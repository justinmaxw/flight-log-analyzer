"""One-command entry point: generate the synthetic bag, then parse and summarize.

    ./.venv/bin/python src/main.py

This is the M1 "run end-to-end" command. Later milestones add detection on top
of the parsed structure.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_bag import generate_bag  # noqa: E402
from parser import format_summary, parse_bag  # noqa: E402


def main() -> None:
    print("== Generating synthetic flight bag ==")
    bag_path = generate_bag()
    print(f"Wrote -> {bag_path}\n")

    print("== Structural parse ==")
    structure = parse_bag(bag_path)
    print(format_summary(structure))


if __name__ == "__main__":
    main()
