#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Compile a YAML/JSON workout plan into a Zwift .zwo file."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

import yaml

from validate_zwo import load_schema, validate_file

ZONE_POWER = {
    "z1": 0.55,
    "z2": 0.65,
    "z3": 0.75,
    "z4": 0.90,
    "z5": 1.05,
    "z6": 1.20,
}


class PlanError(ValueError):
    pass


def load_plan(path: Path) -> dict[str, Any]:
    text = path.read_text()
    if path.suffix.lower() in {".json"}:
        return json.loads(text)
    return yaml.safe_load(text)


def slugify(name: str) -> str:
    import re

    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "workout"


def to_seconds(minutes: float | int | None) -> int:
    if minutes is None:
        return 0
    return int(round(float(minutes) * 60))


def power_to_ratio(value: Any, ftp: float | None, field: str) -> tuple[float | None, float | None, bool]:
    if value is None:
        return None, None, False

    if isinstance(value, list) and len(value) == 2:
        low = power_to_ratio(value[0], ftp, field)[0]
        high = power_to_ratio(value[1], ftp, field)[0]
        return low, high, True

    if isinstance(value, str):
        key = value.lower().strip()
        if key in ZONE_POWER:
            return ZONE_POWER[key], None, False
        raise PlanError(f"Unsupported power string for {field}: {value}")

    if isinstance(value, dict):
        if "pct" in value:
            return float(value["pct"]) / 100.0, None, False
        if "watts" in value:
            if not ftp:
                raise PlanError(f"FTP required for watts in {field}")
            return float(value["watts"]) / float(ftp), None, False
        raise PlanError(f"Unsupported power dict for {field}: {value}")

    return float(value), None, False


def require_power(value: float | None, field: str) -> float:
    if value is None:
        raise PlanError(f"{field} is required")
    return float(value)


def standard_warmup() -> list[dict[str, Any]]:
    return [
        {"tag": "Warmup", "Duration": 600, "PowerLow": 0.5, "PowerHigh": 0.77},
        {"tag": "FreeRide", "Duration": 60, "FlatRoad": 1, "Cadence": 110},
        {"tag": "SteadyState", "Duration": 60, "Power": 0.5},
        {"tag": "FreeRide", "Duration": 60, "FlatRoad": 1, "Cadence": 110},
        {"tag": "SteadyState", "Duration": 60, "Power": 0.5},
    ]


def emit_block(workout_el: ET.Element, block: dict[str, Any], ftp: float | None) -> None:
    block_type = block.get("type")
    if not block_type:
        raise PlanError("Block missing type")

    if block_type == "standard_warmup":
        for b in standard_warmup():
            tag = b.pop("tag")
            ET.SubElement(workout_el, tag, {k: str(v) for k, v in b.items()})
        return

    if block_type == "repeat":
        times = int(block.get("times", 0))
        if times <= 0:
            raise PlanError("repeat.times must be > 0")
        for _ in range(times):
            for child in block.get("blocks", []):
                emit_block(workout_el, child, ftp)
        return

    if block_type in {"warmup", "cooldown", "ramp"}:
        tag = block_type.capitalize()
        duration = to_seconds(block.get("minutes")) or int(block.get("seconds", 0))
        if duration <= 0:
            raise PlanError(f"{block_type} requires minutes or seconds")

        power_low, power_high, is_range = power_to_ratio(block.get("power"), ftp, "power")
        if not is_range:
            power_low = block.get("power_low", power_low)
            power_high = block.get("power_high", power_high)
            if power_low is None or power_high is None:
                raise PlanError(f"{block_type} requires power_low/power_high or power range")

        attrs: dict[str, str] = {
            "Duration": str(duration),
            "PowerLow": f"{require_power(power_low, 'power_low'):.4f}",
            "PowerHigh": f"{require_power(power_high, 'power_high'):.4f}",
        }
        if "cadence" in block:
            attrs["Cadence"] = str(int(block["cadence"]))
        ET.SubElement(workout_el, tag, attrs)
        return

    if block_type == "steadystate":
        duration = to_seconds(block.get("minutes")) or int(block.get("seconds", 0))
        if duration <= 0:
            raise PlanError("steady requires minutes or seconds")
        power, _, _ = power_to_ratio(block.get("power"), ftp, "power")
        if power is None:
            raise PlanError("steady requires power")
        attrs = {"Duration": str(duration), "Power": f"{float(power):.4f}"}
        if "cadence" in block:
            attrs["Cadence"] = str(int(block["cadence"]))
        ET.SubElement(workout_el, "SteadyState", attrs)
        return

    if block_type == "freeride":
        duration = to_seconds(block.get("minutes")) or int(block.get("seconds", 0))
        if duration <= 0:
            raise PlanError("freeride requires minutes or seconds")
        attrs = {"Duration": str(duration)}
        if "flat_road" in block:
            attrs["FlatRoad"] = str(int(block["flat_road"]))
        if "cadence" in block:
            attrs["Cadence"] = str(int(block["cadence"]))
        ET.SubElement(workout_el, "FreeRide", attrs)
        return

    if block_type == "intervals":
        repeat = int(block.get("repeat", 0))
        if repeat <= 0:
            raise PlanError("intervals requires repeat")
        on_seconds = to_seconds(block.get("on_minutes")) or int(block.get("on_seconds", 0))
        off_seconds = to_seconds(block.get("off_minutes")) or int(block.get("off_seconds", 0))
        if on_seconds <= 0 or off_seconds <= 0:
            raise PlanError("intervals requires on/off duration")

        on_power = block.get("on_power")
        off_power = block.get("off_power")

        on_low, on_high, on_is_range = power_to_ratio(on_power, ftp, "on_power")
        off_low, off_high, off_is_range = power_to_ratio(off_power, ftp, "off_power")

        attrs: dict[str, str] = {
            "Repeat": str(repeat),
            "OnDuration": str(on_seconds),
            "OffDuration": str(off_seconds),
        }

        if on_is_range:
            attrs["PowerOnLow"] = f"{require_power(on_low, 'on_power_low'):.4f}"
            attrs["PowerOnHigh"] = f"{require_power(on_high, 'on_power_high'):.4f}"
        elif on_low is not None:
            attrs["OnPower"] = f"{float(on_low):.4f}"

        if off_is_range:
            attrs["PowerOffLow"] = f"{require_power(off_low, 'off_power_low'):.4f}"
            attrs["PowerOffHigh"] = f"{require_power(off_high, 'off_power_high'):.4f}"
        elif off_low is not None:
            attrs["OffPower"] = f"{float(off_low):.4f}"

        if "cadence" in block:
            attrs["Cadence"] = str(int(block["cadence"]))
        if "cadence_rest" in block:
            attrs["CadenceResting"] = str(int(block["cadence_rest"]))

        ET.SubElement(workout_el, "IntervalsT", attrs)
        return

    if block_type == "maxeffort":
        duration = to_seconds(block.get("minutes")) or int(block.get("seconds", 0))
        if duration <= 0:
            raise PlanError("maxeffort requires minutes or seconds")
        ET.SubElement(workout_el, "MaxEffort", {"Duration": str(duration)})
        return

    if block_type == "textevent":
        time_offset = int(block.get("time_offset", 0))
        message = block.get("message")
        if not message:
            raise PlanError("textevent requires message")
        ET.SubElement(
            workout_el,
            "textevent",
            {"timeoffset": str(time_offset), "message": str(message)},
        )
        return

    raise PlanError(f"Unsupported block type: {block_type}")


def compile_plan(plan: dict[str, Any]) -> ET.ElementTree:
    name = plan.get("name")
    if not name:
        raise PlanError("plan.name is required")

    author = plan.get("author", "creating-zwift-workout")
    description = plan.get("description", "")
    sport = plan.get("sport", "bike")
    ftp = plan.get("ftp")

    workout = ET.Element("workout_file")
    ET.SubElement(workout, "author").text = str(author)
    ET.SubElement(workout, "name").text = str(name)
    ET.SubElement(workout, "description").text = str(description)
    ET.SubElement(workout, "sportType").text = str(sport)

    tags = ET.SubElement(workout, "tags")
    for tag in plan.get("tags", ["CUSTOM"]):
        ET.SubElement(tags, "tag", {"name": str(tag)})

    workout_el = ET.SubElement(workout, "workout")
    for block in plan.get("blocks", []):
        emit_block(workout_el, block, ftp)

    return ET.ElementTree(workout)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a workout plan to .zwo")
    parser.add_argument("--plan", required=True, help="Path to YAML/JSON plan")
    parser.add_argument("--output", default="workouts", help="Output directory")
    parser.add_argument("--validate", action="store_true", help="Validate .zwo output")

    args = parser.parse_args()
    plan_path = Path(args.plan)
    output_dir = Path(args.output)

    if not plan_path.exists():
        print(f"error: missing plan {plan_path}", file=sys.stderr)
        return 2

    plan = load_plan(plan_path)
    tree = compile_plan(plan)

    output_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(str(plan.get("name")))
    output_path = output_dir / f"{slug}.zwo"
    root = tree.getroot()
    if root is None:
        raise PlanError("failed to build workout XML")
    output_path.write_text(ET.tostring(root, encoding="unicode"))

    if args.validate:
        tag_attr_usage = Path("sub/zwift-workout-file-reference/tag_attr_usage.json")
        descriptions = Path("sub/zwift-workout-file-reference/descriptions.yaml")
        allowed_tags, allowed_attrs_global, allowed_attrs_by_tag = load_schema(
            tag_attr_usage, descriptions
        )
        errors, warnings = validate_file(
            output_path, allowed_tags, allowed_attrs_global, allowed_attrs_by_tag
        )
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        for warning in warnings:
            print(warning, file=sys.stderr)

    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
