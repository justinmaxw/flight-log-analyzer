"""Structural parser for rosbag2 bags.

Opens ANY rosbag2 bag and reports its layout: topics, message types, per-topic
message counts, total duration, and start/end timestamps. Also extracts the
altitude time series from any PoseStamped topic to set up M2's altitude-drop
detector. Structure reporting is type-agnostic (works on arbitrary bags);
only altitude extraction deserializes messages, and only for PoseStamped topics.

Verified against rosbags 0.11.3 Reader API (connections[].topic/.msgtype/.msgcount,
reader.duration/.start_time/.end_time in nanoseconds, messages() yields
(connection, timestamp_ns, rawdata)).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_typestore

POSE_TYPE = "geometry_msgs/msg/PoseStamped"


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
        pose_conns = [c for c in reader.connections if c.msgtype == POSE_TYPE]
        if pose_conns:
            for connection, timestamp, rawdata in reader.messages(connections=pose_conns):
                msg = typestore.deserialize_cdr(rawdata, connection.msgtype)
                t_rel = (timestamp - start_ns) / 1e9
                altitude.append((t_rel, float(msg.pose.position.z)))
            altitude.sort(key=lambda p: p[0])

        return BagStructure(
            path=str(path),
            topics=topics,
            message_count=reader.message_count,
            duration_s=reader.duration / 1e9,
            start_time_ns=reader.start_time,
            end_time_ns=reader.end_time,
            altitude_series=altitude,
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
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse a rosbag2 bag and print its structure.")
    ap.add_argument("path", help="path to a rosbag2 bag directory")
    args = ap.parse_args()
    print(format_summary(parse_bag(args.path)))


if __name__ == "__main__":
    main()
