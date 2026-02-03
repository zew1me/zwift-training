#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Create a Zwift .zwo workout from plain text and validate it."""
from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

from validate_zwo import load_schema, validate_file

STANDARD_COOLDOWN_SECONDS = 600
MIN_COOLDOWN_SECONDS = 300

ZONE_POWER = {
    "z1": 0.55,
    "z2": 0.65,
    "z3": 0.75,
    "z4": 0.90,
    "z5": 1.05,
    "z6": 1.20,
}


def parse_total_minutes(text: str) -> int | None:
    text = text.lower()
    total_minutes = 0

    range_minutes = re.findall(r"(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)\s*(?:min|minutes|m)\b", text)
    if range_minutes:
        total_minutes += int(float(range_minutes[-1][1]))

    single_minutes = re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:min|minutes|m)\b", text)
    if single_minutes:
        total_minutes += int(float(single_minutes[-1]))

    range_hours = re.findall(r"(\d+(?:\.\d+)?)\s*[–-]\s*(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|h)\b", text)
    if range_hours:
        total_minutes += int(float(range_hours[-1][1]) * 60)

    single_hours = re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:hour|hours|hr|h)\b", text)
    if single_hours:
        total_minutes += int(float(single_hours[-1]) * 60)

    return total_minutes or None


def parse_tss(text: str) -> float | None:
    match = re.search(r"\btss\b[^0-9]*([0-9]+(?:\.\d+)?)", text.lower())
    if not match:
        return None
    return float(match.group(1))


def parse_cooldown_minutes(text: str) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:min|minutes|m)\s*(?:cooldown|cool down)", text.lower())
    if not match:
        return None
    return int(float(match.group(1)))


def parse_ftp(text: str) -> float | None:
    match = re.search(r"\bftp\b[^0-9]*([0-9]+(?:\.\d+)?)", text.lower())
    if not match:
        return None
    return float(match.group(1))


def parse_zone(text: str) -> str | None:
    match = re.search(r"\b(z[1-6])\b", text.lower())
    if not match:
        return None
    return match.group(1)


@dataclass
class IntervalBlock:
    repeat: int
    on_seconds: int
    on_power: float | None
    off_seconds: int
    off_power: float | None
    on_power_low: float | None = None
    on_power_high: float | None = None
    off_power_low: float | None = None
    off_power_high: float | None = None
    cadence: int | None = None
    cadence_resting: int | None = None


@dataclass
class SetBlock:
    repeat: int
    interval: IntervalBlock
    rest_between_sets_seconds: int


def parse_intervals(text: str, ftp: float | None) -> tuple[list[IntervalBlock], list[SetBlock]]:
    text_lower = text.lower()
    interval_blocks: list[IntervalBlock] = []
    set_blocks: list[SetBlock] = []

    cadence_work = None
    cadence_rest = None
    rest_cadence_match = re.search(
        r"(rest cadence|cadence rest|rbi cadence)\s*(\d+)(?:\s*[–-]\s*(\d+))?",
        text_lower,
    )
    if rest_cadence_match:
        cadence_rest = int(rest_cadence_match.group(2))
    cadence_match = re.search(
        r"\bcadence\b\s*(\d+)(?:\s*[–-]\s*(\d+))?", text_lower
    )
    if cadence_match:
        cadence_work = int(cadence_match.group(1))

    set_pattern = re.compile(
        r"(\d+)\s*[x×]\s*\[\s*(\d+)\s*[x×]\s*(\d+)\s*[′']\s*(?:@[^\]]+)?\s*(\d+)\s*[′']\s*rbi\s*\]\s*(\d+)\s*[′']\s*rbs",
        re.IGNORECASE,
    )
    set_match = set_pattern.search(text)
    if set_match:
        sets = int(set_match.group(1))
        reps = int(set_match.group(2))
        on_minutes = int(set_match.group(3))
        rbi_minutes = int(set_match.group(4))
        rbs_minutes = int(set_match.group(5))
        on_power = 1.05
        set_blocks.append(
            SetBlock(
                repeat=sets,
                interval=IntervalBlock(
                    repeat=reps,
                    on_seconds=on_minutes * 60,
                    on_power=on_power,
                    off_seconds=rbi_minutes * 60,
                    off_power=0.5,
                    cadence=cadence_work,
                    cadence_resting=cadence_rest,
                ),
                rest_between_sets_seconds=rbs_minutes * 60,
            )
        )
        return interval_blocks, set_blocks

    interval_pattern = re.compile(
        r"(\d+)(?:\s*[–-]\s*(\d+))?\s*[x×]\s*(\d+)\s*[′']\s*@\s*([0-9.]+)(?:\s*[–-]\s*([0-9.]+))?\s*(%|percent|w|watts)?",
        re.IGNORECASE,
    )

    for match in interval_pattern.finditer(text):
        repeat_min = int(match.group(1))
        repeat_max = int(match.group(2) or match.group(1))
        repeat = repeat_max
        on_minutes = int(match.group(3))
        p_low = float(match.group(4))
        p_high = float(match.group(5) or match.group(4))
        unit = match.group(6) or ("%" if "%" in match.group(0) else "")

        if unit in {"%", "percent"}:
            on_power_low = p_low / 100.0
            on_power_high = p_high / 100.0
        elif unit in {"w", "watts"}:
            if not ftp:
                raise ValueError("FTP is required when using watt-based intervals")
            on_power_low = p_low / ftp
            on_power_high = p_high / ftp
        else:
            raise ValueError("Could not determine interval units; use % of FTP or watts")

        on_power = None
        if on_power_low == on_power_high:
            on_power = on_power_low

        interval_blocks.append(
            IntervalBlock(
                repeat=repeat,
                on_seconds=on_minutes * 60,
                on_power=on_power,
                off_seconds=on_minutes * 60,
                off_power=0.5,
                on_power_low=on_power_low,
                on_power_high=on_power_high,
                cadence=cadence_work,
                cadence_resting=cadence_rest,
            )
        )

    return interval_blocks, set_blocks


def standard_warmup(total_minutes: int | None) -> list[dict]:
    short = total_minutes is not None and total_minutes < 45
    warmup_blocks = []
    if short:
        warmup_blocks.append({"tag": "Warmup", "Duration": 300, "PowerLow": 0.5, "PowerHigh": 0.77})
    else:
        warmup_blocks.append({"tag": "Warmup", "Duration": 600, "PowerLow": 0.5, "PowerHigh": 0.77})

    warmup_blocks.extend(
        [
            {"tag": "FreeRide", "Duration": 60, "FlatRoad": 1, "Cadence": 110},
            {"tag": "SteadyState", "Duration": 60, "Power": 0.5},
            {"tag": "FreeRide", "Duration": 60, "FlatRoad": 1, "Cadence": 110},
            {"tag": "SteadyState", "Duration": 60, "Power": 0.5},
        ]
    )
    return warmup_blocks


def cooldown_block(seconds: int) -> dict:
    return {"tag": "Cooldown", "Duration": seconds, "PowerLow": 0.65, "PowerHigh": 0.45}


def tss_to_intensity(tss: float, duration_seconds: int) -> float:
    if duration_seconds <= 0:
        return 0.65
    intensity = math.sqrt((tss * 3600.0) / (duration_seconds * 100.0))
    return max(0.45, min(1.1, intensity))


def build_workout(text: str, name: str, author: str, output_path: Path) -> None:
    total_minutes = parse_total_minutes(text)
    tss = parse_tss(text)
    cooldown_minutes = parse_cooldown_minutes(text)
    ftp = parse_ftp(text)
    zone = parse_zone(text)

    interval_blocks, set_blocks = parse_intervals(text, ftp)

    warmup = standard_warmup(total_minutes)
    warmup_seconds = sum(block["Duration"] for block in warmup)

    cooldown_seconds = (cooldown_minutes or (STANDARD_COOLDOWN_SECONDS // 60)) * 60
    cooldown_seconds = max(MIN_COOLDOWN_SECONDS, cooldown_seconds)

    intervals_seconds = 0
    for block in interval_blocks:
        intervals_seconds += block.repeat * (block.on_seconds + block.off_seconds)
    for set_block in set_blocks:
        intervals_seconds += set_block.repeat * (
            set_block.interval.repeat * (set_block.interval.on_seconds + set_block.interval.off_seconds)
            + set_block.rest_between_sets_seconds
        )

    total_seconds = total_minutes * 60 if total_minutes else None

    base_seconds = 0
    if total_seconds is not None:
        base_seconds = total_seconds - warmup_seconds - cooldown_seconds - intervals_seconds
        if base_seconds < 0:
            cooldown_seconds = MIN_COOLDOWN_SECONDS
            base_seconds = total_seconds - warmup_seconds - cooldown_seconds - intervals_seconds
        if base_seconds < 0:
            raise ValueError("Not enough time for warmup/intervals/cooldown")

    if zone and zone in ZONE_POWER:
        base_power = ZONE_POWER[zone]
    elif tss and total_seconds:
        base_power = tss_to_intensity(tss, total_seconds)
    else:
        base_power = 0.65

    workout = ET.Element("workout_file")
    ET.SubElement(workout, "author").text = author
    ET.SubElement(workout, "name").text = name
    ET.SubElement(workout, "description").text = text
    ET.SubElement(workout, "sportType").text = "bike"
    tags = ET.SubElement(workout, "tags")
    ET.SubElement(tags, "tag", {"name": "CUSTOM"})
    workout_el = ET.SubElement(workout, "workout")

    for block in warmup:
        tag = block.pop("tag")
        ET.SubElement(workout_el, tag, {k: str(v) for k, v in block.items()})

    if base_seconds > 0:
        ET.SubElement(workout_el, "SteadyState", {"Duration": str(base_seconds), "Power": f"{base_power:.4f}"})

    for block in interval_blocks:
        attrs = {
            "Repeat": str(block.repeat),
            "OnDuration": str(block.on_seconds),
            "OffDuration": str(block.off_seconds),
        }
        if block.on_power is not None:
            attrs["OnPower"] = f"{block.on_power:.4f}"
        if block.off_power is not None:
            attrs["OffPower"] = f"{block.off_power:.4f}"
        if block.on_power_low is not None:
            attrs["PowerOnLow"] = f"{block.on_power_low:.4f}"
        if block.on_power_high is not None:
            attrs["PowerOnHigh"] = f"{block.on_power_high:.4f}"
        if block.off_power_low is not None:
            attrs["PowerOffLow"] = f"{block.off_power_low:.4f}"
        if block.off_power_high is not None:
            attrs["PowerOffHigh"] = f"{block.off_power_high:.4f}"
        if block.cadence is not None:
            attrs["Cadence"] = str(block.cadence)
        if block.cadence_resting is not None:
            attrs["CadenceResting"] = str(block.cadence_resting)
        ET.SubElement(workout_el, "IntervalsT", attrs)

    for set_block in set_blocks:
        for _ in range(set_block.repeat):
            attrs = {
                "Repeat": str(set_block.interval.repeat),
                "OnDuration": str(set_block.interval.on_seconds),
                "OffDuration": str(set_block.interval.off_seconds),
            }
            if set_block.interval.on_power is not None:
                attrs["OnPower"] = f"{set_block.interval.on_power:.4f}"
            if set_block.interval.off_power is not None:
                attrs["OffPower"] = f"{set_block.interval.off_power:.4f}"
            if set_block.interval.on_power_low is not None:
                attrs["PowerOnLow"] = f"{set_block.interval.on_power_low:.4f}"
            if set_block.interval.on_power_high is not None:
                attrs["PowerOnHigh"] = f"{set_block.interval.on_power_high:.4f}"
            if set_block.interval.off_power_low is not None:
                attrs["PowerOffLow"] = f"{set_block.interval.off_power_low:.4f}"
            if set_block.interval.off_power_high is not None:
                attrs["PowerOffHigh"] = f"{set_block.interval.off_power_high:.4f}"
            if set_block.interval.cadence is not None:
                attrs["Cadence"] = str(set_block.interval.cadence)
            if set_block.interval.cadence_resting is not None:
                attrs["CadenceResting"] = str(set_block.interval.cadence_resting)
            ET.SubElement(workout_el, "IntervalsT", attrs)
            ET.SubElement(
                workout_el,
                "SteadyState",
                {"Duration": str(set_block.rest_between_sets_seconds), "Power": "0.5"},
            )

    ET.SubElement(workout_el, "Cooldown", {k: str(v) for k, v in cooldown_block(cooldown_seconds).items() if k != "tag"})

    tree = ET.ElementTree(workout)
    output_path.write_text(ET.tostring(workout, encoding="unicode"))


def slugify(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip())
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "workout"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Zwift .zwo file from plain text")
    parser.add_argument("--text", required=True, help="Plain text workout description")
    parser.add_argument("--name", help="Workout name (defaults to derived slug)")
    parser.add_argument("--author", default="creating-zwift-workout")
    parser.add_argument("--output-dir", default="workouts")
    parser.add_argument(
        "--validate", action="store_true", help="Run strict validator after writing"
    )

    args = parser.parse_args()
    name = args.name or args.text
    slug = slugify(name)
    output_path = Path(args.output_dir) / f"{slug}.zwo"

    try:
        build_workout(args.text, name, args.author, output_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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
