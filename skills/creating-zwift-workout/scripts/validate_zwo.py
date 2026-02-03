#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Strict validator for Zwift .zwo files using the subtree reference."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

import yaml


def load_schema(tag_attr_usage_path: Path, descriptions_path: Path) -> tuple[set[str], set[str], dict[str, set[str]]]:
    usage = json.loads(tag_attr_usage_path.read_text())
    elements = usage.get("elements", [])
    attributes = usage.get("attributes", [])

    allowed_tags = {e["tag"] for e in elements if "tag" in e}
    allowed_attrs_global = {a["attribute"] for a in attributes if "attribute" in a}

    allowed_attrs_by_tag: dict[str, set[str]] = {}
    for e in elements:
        tag = e.get("tag")
        attrs = e.get("attributes") or []
        if tag:
            allowed_attrs_by_tag[tag] = set(attrs)

    desc = yaml.safe_load(descriptions_path.read_text()) or {}
    allowed_tags |= set((desc.get("elements") or {}).keys())
    allowed_attrs_global |= set((desc.get("attributes") or {}).keys())

    return allowed_tags, allowed_attrs_global, allowed_attrs_by_tag


def iter_zwo_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for item in sorted(path.rglob("*.zwo")):
        if item.is_file():
            yield item


def validate_file(
    path: Path,
    allowed_tags: set[str],
    allowed_attrs_global: set[str],
    allowed_attrs_by_tag: dict[str, set[str]],
    warn_on_mismatch: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return [f"{path}: XML parse error: {exc}"], warnings

    root = tree.getroot()
    if root.tag != "workout_file":
        errors.append(f"{path}: root tag is '{root.tag}', expected 'workout_file'")

    if root.find("workout") is None:
        errors.append(f"{path}: missing <workout> element")

    for elem in root.iter():
        if elem.tag not in allowed_tags:
            errors.append(f"{path}: unknown element <{elem.tag}>")
            continue

        allowed_attrs = allowed_attrs_by_tag.get(elem.tag)
        for attr in elem.attrib.keys():
            if attr not in allowed_attrs_global:
                errors.append(f"{path}: unknown attribute '{attr}' on <{elem.tag}>")
                continue
            if allowed_attrs is not None and len(allowed_attrs) > 0:
                if attr not in allowed_attrs and warn_on_mismatch:
                    warnings.append(
                        f"{path}: attribute '{attr}' not listed for <{elem.tag}> in tag_attr_usage.json"
                    )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate .zwo files against subtree schema")
    parser.add_argument("--path", required=True, help="File or directory containing .zwo files")
    parser.add_argument(
        "--tag-attr-usage",
        default="sub/zwift-workout-file-reference/tag_attr_usage.json",
        help="Path to tag_attr_usage.json",
    )
    parser.add_argument(
        "--descriptions",
        default="sub/zwift-workout-file-reference/descriptions.yaml",
        help="Path to descriptions.yaml",
    )
    parser.add_argument(
        "--warn-mismatch",
        action="store_true",
        help="Warn when attributes are not listed for a tag in tag_attr_usage.json",
    )

    args = parser.parse_args()
    base = Path(args.path)
    tag_attr_usage = Path(args.tag_attr_usage)
    descriptions = Path(args.descriptions)

    if not tag_attr_usage.exists():
        print(f"error: missing {tag_attr_usage}", file=sys.stderr)
        return 2
    if not descriptions.exists():
        print(f"error: missing {descriptions}", file=sys.stderr)
        return 2

    allowed_tags, allowed_attrs_global, allowed_attrs_by_tag = load_schema(
        tag_attr_usage, descriptions
    )

    files = list(iter_zwo_files(base))
    if not files:
        print("error: no .zwo files found", file=sys.stderr)
        return 2

    all_errors: list[str] = []
    all_warnings: list[str] = []
    for file_path in files:
        errors, warnings = validate_file(
            file_path,
            allowed_tags,
            allowed_attrs_global,
            allowed_attrs_by_tag,
            warn_on_mismatch=args.warn_mismatch,
        )
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    if all_errors:
        for err in all_errors:
            print(err, file=sys.stderr)
        print(f"validation failed: {len(all_errors)} error(s)", file=sys.stderr)
        return 1

    for warning in all_warnings:
        print(warning, file=sys.stderr)
    print(f"validation ok: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
