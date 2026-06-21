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
| **M2** | Altitude-drop detector | ✅ done |
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

# Detect altitude drops in any bag (tunable thresholds):
./.venv/bin/python src/detector.py path/to/bag_dir --min-drop 5 --min-rate 2

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

== Altitude-drop detection ==
Altitude-drop detector (>= 5 m loss at >= 2 m/s):
  [1] -15.0 m drop over 2.0 s (7.5 m/s): 50.0 m -> 34.9 m, t=30.0->32.0 s
```

## Architecture

```
src/
  generate_bag.py   Writes a deterministic synthetic rosbag2 bag with an
                    injected altitude-drop anomaly (ground truth for detectors).
  parser.py         Type-agnostic structural reader: topics, msg types, counts,
                    duration, start/end; extracts altitude series from PoseStamped.
  detector.py       Altitude-drop detector: bounded-lookback descent scan over the
                    altitude series -> rapid-loss events (drop, rate, peak->trough).
  main.py           One-command: generate -> parse -> summarize -> detect.
tests/              pytest: bag contents + parser structure + injected-drop check
                    + detector (finds the anomaly, rejects climbs/flat/gentle).
```

The parser separates **structure** (works on any bag, no deserialization) from
**signal extraction** (altitude series), so detectors layer on top without
changing the reader.

### How the altitude-drop detector works

For each altitude sample it looks back over a short window (`window_s`, default
3 s), finds the recent high, and measures the loss and descent rate from it. A
sample is flagged only when it has lost ≥ `min_drop_m` (5 m) at ≥ `min_rate_mps`
(2 m/s); consecutive flagged samples become one event, reported at its deepest
point. The lookback is **bounded** so an unrelated earlier high isn't charged
against a later drop, and the "recent high" is pinned to the *last* moment at
altitude before the descent — otherwise sensor noise on a long cruise plateau
inflates the measured duration and hides a genuinely rapid drop.

**Detector thresholds — "Decisions to sanity-check"** (assumptions, tunable via
CLI): `min_drop_m=5`, `min_rate_mps=2`, `window_s=3`, `peak_tol_m=0.5`. Chosen so
the injected ~15 m / ~2 s (~7.5 m/s) anomaly is caught with margin while sensor
noise (~0.05 m) and gentle descents are not. Real thresholds should be set per
airframe and flight envelope.

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
