"""Generate a synthetic ROS2 (rosbag2) bag for the Flight Log Analyzer.

Milestone 1: produce a deterministic synthetic flight log containing an
*injected altitude-drop anomaly*, so later milestones have a known ground truth
to detect against. Detection itself is NOT done here (that is M2/M4).

Schema (documented standard ROS2 types — see README "Decisions to sanity-check"):
  /flight/pose : geometry_msgs/msg/PoseStamped  (altitude = pose.position.z, meters)
  /flight/imu  : sensor_msgs/msg/Imu            (linear_acceleration m/s^2, angular_velocity rad/s)

Verified against rosbags 0.11.3 (Writer requires version=8|9; serialize_cdr(msg, typename)).
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
from rosbags.rosbag2 import Writer
from rosbags.typesys import Stores, get_typestore

POSE_TOPIC = "/flight/pose"
POSE_TYPE = "geometry_msgs/msg/PoseStamped"
IMU_TOPIC = "/flight/imu"
IMU_TYPE = "sensor_msgs/msg/Imu"
DEFAULT_OUT = "data/synthetic_flight"

# Injected altitude profile keyframes: (time_s, altitude_m). Linearly interpolated.
# Smooth climb -> cruise -> sharp 15 m drop over 2 s at t=30 -> partial recovery.
_ALT_KEYFRAMES = [
    (0.0, 0.0),
    (10.0, 50.0),   # climb to cruise altitude
    (30.0, 50.0),   # steady cruise
    (32.0, 35.0),   # ANOMALY: -15 m over 2 s
    (40.0, 45.0),   # partial recovery
    (60.0, 45.0),   # cruise to end
]


def _altitude(t: float) -> float:
    """Piecewise-linear altitude (m) at flight time ``t`` seconds."""
    ks = _ALT_KEYFRAMES
    if t <= ks[0][0]:
        return ks[0][1]
    if t >= ks[-1][0]:
        return ks[-1][1]
    for (t0, a0), (t1, a1) in zip(ks, ks[1:]):
        if t0 <= t <= t1:
            frac = (t - t0) / (t1 - t0)
            return a0 + frac * (a1 - a0)
    return ks[-1][1]


def generate_bag(
    out_dir: str | Path = DEFAULT_OUT,
    duration_s: float = 60.0,
    pose_hz: float = 10.0,
    imu_hz: float = 50.0,
    seed: int = 42,
    overwrite: bool = True,
) -> Path:
    """Write a synthetic rosbag2 bag and return its path.

    Deterministic given ``seed`` so unit tests can assert on the contents.
    """
    out = Path(out_dir).resolve()
    if out.exists():
        if not overwrite:
            raise FileExistsError(f"{out} exists (pass overwrite=True)")
        # Safety: only clobber a directory that is empty or is itself a prior bag
        # (has metadata.yaml or a .db3), so we never delete an unrelated folder.
        looks_like_bag = (out / "metadata.yaml").exists() or any(out.glob("*.db3"))
        if not (looks_like_bag or not any(out.iterdir())):
            raise ValueError(f"refusing to overwrite non-bag directory: {out}")
        shutil.rmtree(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    ts = get_typestore(Stores.ROS2_HUMBLE)
    T = lambda name: ts.types[name]  # noqa: E731 - tiny local factory alias

    def stamp(ns: int):
        return T("builtin_interfaces/msg/Time")(sec=ns // 10**9, nanosec=ns % 10**9)

    def header(ns: int, frame_id: str):
        return T("std_msgs/msg/Header")(stamp=stamp(ns), frame_id=frame_id)

    def pose_msg(ns: int, t: float):
        return T(POSE_TYPE)(
            header=header(ns, "map"),
            pose=T("geometry_msgs/msg/Pose")(
                position=T("geometry_msgs/msg/Point")(
                    x=2.0 * t + rng.normal(0, 0.05),     # ~2 m/s forward
                    y=rng.normal(0, 0.05),
                    z=_altitude(t) + rng.normal(0, 0.05),
                ),
                orientation=T("geometry_msgs/msg/Quaternion")(x=0.0, y=0.0, z=0.0, w=1.0),
            ),
        )

    def imu_msg(ns: int):
        # Raw IMU: gravity on +z, small noise. orientation_covariance[0]=-1 per
        # REP-145 meaning "no orientation estimate". No IMU spike injected (that is M4).
        ocov = np.zeros(9, dtype=np.float64)
        ocov[0] = -1.0
        return T(IMU_TYPE)(
            header=header(ns, "imu_link"),
            orientation=T("geometry_msgs/msg/Quaternion")(x=0.0, y=0.0, z=0.0, w=1.0),
            orientation_covariance=ocov,
            angular_velocity=T("geometry_msgs/msg/Vector3")(
                x=rng.normal(0, 0.01), y=rng.normal(0, 0.01), z=rng.normal(0, 0.01)
            ),
            angular_velocity_covariance=np.zeros(9, dtype=np.float64),
            linear_acceleration=T("geometry_msgs/msg/Vector3")(
                x=rng.normal(0, 0.10), y=rng.normal(0, 0.10), z=9.81 + rng.normal(0, 0.10)
            ),
            linear_acceleration_covariance=np.zeros(9, dtype=np.float64),
        )

    # Build all timestamped events, then write in chronological order.
    events: list[tuple[int, str, object]] = []
    n_pose = int(round(duration_s * pose_hz))
    n_imu = int(round(duration_s * imu_hz))
    for i in range(n_pose):
        t = i / pose_hz
        ns = int(round(t * 1e9))
        events.append((ns, POSE_TOPIC, pose_msg(ns, t)))
    for i in range(n_imu):
        t = i / imu_hz
        ns = int(round(t * 1e9))
        events.append((ns, IMU_TOPIC, imu_msg(ns)))
    events.sort(key=lambda e: e[0])

    writer = Writer(out, version=9)
    writer.open()
    try:
        conns = {
            POSE_TOPIC: writer.add_connection(POSE_TOPIC, POSE_TYPE, typestore=ts),
            IMU_TOPIC: writer.add_connection(IMU_TOPIC, IMU_TYPE, typestore=ts),
        }
        typename = {POSE_TOPIC: POSE_TYPE, IMU_TOPIC: IMU_TYPE}
        for ns, topic, msg in events:
            writer.write(conns[topic], ns, ts.serialize_cdr(msg, typename[topic]))
    finally:
        writer.close()

    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a synthetic rosbag2 flight log.")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output bag directory")
    ap.add_argument("--duration", type=float, default=60.0, help="flight duration (s)")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = ap.parse_args()
    path = generate_bag(args.out, duration_s=args.duration, seed=args.seed)
    print(f"Wrote synthetic bag -> {path}")
    print(f"  contents: {sorted(p.name for p in path.iterdir())}")


if __name__ == "__main__":
    main()
