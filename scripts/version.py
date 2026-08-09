#!/usr/bin/env python3
"""Read the repository version and optionally sync a Home Assistant manifest."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "version.json"
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def get_version() -> str:
    with VERSION_FILE.open(encoding="utf-8") as file:
        data = json.load(file)

    fields = ("major", "minor", "patch")
    if any(not isinstance(data.get(field), int) or data[field] < 0 for field in fields):
        raise ValueError("version.json must contain non-negative integer major, minor, and patch fields")

    version = ".".join(str(data[field]) for field in fields)
    if not SEMVER_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid version: {version}")
    return version


def sync_manifest(path: Path, version: str) -> None:
    contents = path.read_text(encoding="utf-8")
    updated, replacements = re.subn(
        r'("version"\s*:\s*)"[^"]+"',
        rf'\1"{version}"',
        contents,
        count=1,
    )
    if replacements != 1:
        raise ValueError(f"Could not find exactly one version field in {path}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-manifest", type=Path)
    args = parser.parse_args()

    version = get_version()
    if args.write_manifest:
        sync_manifest(args.write_manifest, version)
    print(version)


if __name__ == "__main__":
    main()
