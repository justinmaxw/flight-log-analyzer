"""One-command entry point: generate the synthetic bag, then parse and summarize.

    ./.venv/bin/python src/main.py

This is the M1 "run end-to-end" command. Later milestones add detection on top
of the parsed structure.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detector import detect_altitude_drops  # noqa: E402
from generate_bag import generate_bag  # noqa: E402
from parser import parse_bag  # noqa: E402
from report import build_report  # noqa: E402


def main() -> None:
    print("== Generating synthetic flight bag ==")
    bag_path = generate_bag()
    print(f"Wrote -> {bag_path}\n")

    structure = parse_bag(bag_path)
    events = detect_altitude_drops(structure.altitude_series)
    print(build_report(structure, events))


if __name__ == "__main__":
    main()
