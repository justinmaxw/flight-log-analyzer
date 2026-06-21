# Flight Log Analyzer

A CLI tool that ingests **ROS2 bag files** and auto-generates a plain-language
**incident report**: what happened during a flight, what looked anomalous
(altitude drop, IMU spike), and a readable summary.

Built with the pure-Python [`rosbags`](https://gitlab.com/ternaris/rosbags)
library — **no full ROS2 install required**.

## Status

| Milestone | Scope | State |
|---|---|---|
| **M1** | Synthetic bag w/ injected anomaly + structural parser | ✅ done |
| M2 | Altitude-drop detector | next |
| M3 | Plain-language report generator | |
| M4 | IMU-spike detector + run any bag | |
| M5 | *(stretch)* Simple UI / CV angle | |

## Quick start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install rosbags pytest

# Generate the synthetic flight bag, then parse + summarize it:
./.venv/bin/python src/main.py

# Parse any existing rosbag2 bag:
./.venv/bin/python src/parser.py path/to/bag_dir

# Tests:
./.venv/bin/python -m pytest -q
```

Example output:

```
Duration: 59.98 s   (3600 messages across 2 topics)
Topics:
  /flight/imu      sensor_msgs/msg/Imu                  3000 msgs
  /flight/pose     geometry_msgs/msg/PoseStamped         600 msgs
Altitude (z): min 0.0 m, max 50.1 m, 600 samples  [feeds M2 altitude-drop detector]
```

## Architecture

```
src/
  generate_bag.py   Writes a deterministic synthetic rosbag2 bag with an
                    injected altitude-drop anomaly (ground truth for detectors).
  parser.py         Type-agnostic structural reader: topics, msg types, counts,
                    duration, start/end; extracts altitude series from PoseStamped.
  main.py           One-command: generate -> parse -> summarize.
tests/              pytest: bag contents + parser structure + injected-drop check.
```

The parser separates **structure** (works on any bag, no deserialization) from
**signal extraction** (altitude series), so later milestones layer detection on
top without changing the reader.

## Synthetic bag schema — "Decisions to sanity-check"

These are **documented standard ROS2 choices**, not invented, but a domain
reviewer should confirm they match the real systems you care about:

| Choice | Value | Note |
|---|---|---|
| Pose topic / type | `/flight/pose` · `geometry_msgs/msg/PoseStamped` | altitude = `pose.position.z` (meters) |
| IMU topic / type | `/flight/imu` · `sensor_msgs/msg/Imu` | `linear_acceleration` m/s², `angular_velocity` rad/s |
| Rates / duration | pose 10 Hz, IMU 50 Hz, ~60 s | → 600 + 3000 = 3600 messages |
| Injected anomaly | ~15 m altitude drop over ~2 s at t≈30 s, partial recovery | M2 detects this |
| IMU convention | gravity on +z (≈9.81); `orientation_covariance[0] = -1` | REP-145 "no orientation estimate"; no IMU spike injected yet (M4) |

Real PX4/MAVROS stacks often publish on names like `/mavros/local_position/pose`
and `/mavros/imu/data` — topic names are configurable, which is why the parser is
generic rather than hard-coded to these.
