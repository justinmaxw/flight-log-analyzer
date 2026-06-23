"""One command to analyze any flight log (Milestone 4).

    # Analyze an existing rosbag2 bag:
    ./.venv/bin/python src/main.py path/to/bag_dir

    # No path -> generate the synthetic demo bag, then analyze it:
    ./.venv/bin/python src/main.py

The full pipeline in one place: parse structure -> extract altitude + IMU
signals -> run both detectors -> render the plain-language incident report.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from detector import detect_altitude_drops  # noqa: E402
from generate_bag import generate_bag  # noqa: E402
from imu_detector import detect_imu_spikes  # noqa: E402
from parser import parse_bag  # noqa: E402
from report import build_report  # noqa: E402


def analyze_bag(bag_path) -> str:
    """Run the full pipeline on a bag and return the incident report string."""
    structure = parse_bag(bag_path)
    drops = detect_altitude_drops(structure.altitude_series)
    spikes = detect_imu_spikes(structure.imu_accel_series)
    return build_report(structure, drops, spikes)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Analyze a ROS2 bag and print a plain-language incident report."
    )
    ap.add_argument(
        "path",
        nargs="?",
        help="path to a rosbag2 bag directory; omit to generate + analyze the demo bag",
    )
    args = ap.parse_args()

    if args.path is None:
        print("== No bag given: generating synthetic demo flight ==")
        bag_path = generate_bag()
        print(f"Wrote -> {bag_path}\n")
    else:
        bag_path = args.path

    print(analyze_bag(bag_path))


if __name__ == "__main__":
    main()
