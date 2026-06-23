"""Structural parser for rosbag2 bags.

Opens ANY rosbag2 bag and reports its layout: topics, message types, per-topic
message counts, total duration, and start/end timestamps. Also extracts two
signal time series for the detectors: altitude from any PoseStamped topic (M2)
and linear-acceleration magnitude from any Imu topic (M4). Structure reporting
is type-agnostic (works on arbitrary bags); only signal extraction deserializes
messages, and only for the PoseStamped / Imu topics it recognises.

Verified against rosbags 0.11.3 Reader API (connections[].topic/.msgtype/.msgcount,
reader.duration/.start_time/.end_time in nanoseconds, messages() yields
(connection, timestamp_ns, rawdata)).
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field
from pathlib import Path

from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

POSE_TYPE = "geometry_msgs/msg/PoseStamped"
IMU_TYPE = "sensor_msgs/msg/Imu"


@dataclass
class TopicInfo:
    topic: str
    msgtype: str
    msgcount: int


@dataclass
class BagStructure:
    path: str
    topics: list[TopicInfo]
    message_count: int
    duration_s: float
    start_time_ns: int
    end_time_ns: int
    # (time_since_start_s, altitude_m) sampled from PoseStamped topic(s), time-sorted.
    altitude_series: list[tuple[float, float]] = field(default_factory=list)
    # (time_since_start_s, |linear_acceleration| m/s^2) from Imu topic(s), time-sorted.
    imu_accel_series: list[tuple[float, float]] = field(default_factory=list)


def parse_bag(path: str | Path, typestore=None) -> BagStructure:
    """Read a rosbag2 bag and return its structural summary."""
    if typestore is None:
        typestore = get_typestore(Stores.ROS2_HUMBLE)

    reader = Reader(Path(path))
    reader.open()
    try:
        topics = [
            TopicInfo(topic=c.topic, msgtype=c.msgtype, msgcount=c.msgcount)
            for c in reader.connections
        ]
        topics.sort(key=lambda t: t.topic)

        start_ns = reader.start_time
        altitude: list[tuple[float, float]] = []
        imu_accel: list[tuple[float, float]] = []
        # One pass over the topics we extract signals from, dispatched by type.
        signal_conns = [
            c for c in reader.connections if c.msgtype in (POSE_TYPE, IMU_TYPE)
        ]
        if signal_conns:
            for connection, timestamp, rawdata in reader.messages(connections=signal_conns):
                msg = typestore.deserialize_cdr(rawdata, connection.msgtype)
                t_rel = (timestamp - start_ns) / 1e9
                if connection.msgtype == POSE_TYPE:
                    altitude.append((t_rel, float(msg.pose.position.z)))
                else:  # IMU_TYPE
                    a = msg.linear_acceleration
                    mag = math.sqrt(a.x * a.x + a.y * a.y + a.z * a.z)
                    imu_accel.append((t_rel, mag))
            altitude.sort(key=lambda p: p[0])
            imu_accel.sort(key=lambda p: p[0])

        return BagStructure(
            path=str(path),
            topics=topics,
            message_count=reader.message_count,
            duration_s=reader.duration / 1e9,
            start_time_ns=reader.start_time,
            end_time_ns=reader.end_time,
            altitude_series=altitude,
            imu_accel_series=imu_accel,
        )
    finally:
        reader.close()


def format_summary(structure: BagStructure) -> str:
    """Render a plain-language structural summary (the M1 user-facing output)."""
    lines = [
        f"Bag: {structure.path}",
        f"Duration: {structure.duration_s:.2f} s   "
        f"({structure.message_count} messages across {len(structure.topics)} topics)",
        "Topics:",
    ]
    for t in structure.topics:
        lines.append(f"  {t.topic:<16} {t.msgtype:<34} {t.msgcount:>6} msgs")
    if structure.altitude_series:
        zs = [z for _, z in structure.altitude_series]
        lines.append(
            f"Altitude (z): min {min(zs):.1f} m, max {max(zs):.1f} m, "
            f"{len(zs)} samples  [feeds M2 altitude-drop detector]"
        )
    if structure.imu_accel_series:
        accs = [a for _, a in structure.imu_accel_series]
        lines.append(
            f"IMU |accel|: min {min(accs):.1f}, max {max(accs):.1f} m/s^2, "
            f"{len(accs)} samples  [feeds M4 IMU-spike detector]"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse a rosbag2 bag and print its structure.")
    ap.add_argument("path", help="path to a rosbag2 bag directory")
    args = ap.parse_args()
    print(format_summary(parse_bag(args.path)))


if __name__ == "__main__":
    main()
