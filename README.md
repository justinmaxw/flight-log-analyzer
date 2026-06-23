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
| **M3** | Plain-language report generator | ✅ done |
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

# Generate a plain-language incident report for any bag:
./.venv/bin/python src/report.py path/to/bag_dir

# Tests:
./.venv/bin/python -m pytest -q
```

Example output (`src/main.py` — generate synthetic bag, then report on it):

```
================================================================
 FLIGHT INCIDENT REPORT
================================================================

Source bag : .../data/synthetic_flight
Flight time: 60.0 s
Data       : 3600 messages across 2 topic(s)
             /flight/imu      3000 msgs (~50 Hz)  sensor_msgs/msg/Imu
             /flight/pose      600 msgs (~10 Hz)  geometry_msgs/msg/PoseStamped

FLIGHT SUMMARY
----------------------------------------------------------------
The log covers 60.0 s of flight with 600 position samples.
Altitude began near 0.0 m and ended near 45.0 m, ranging from a low
of 0.0 m to a high of 50.1 m.

FINDINGS
----------------------------------------------------------------
1 rapid altitude drop flagged:

[1] SEVERITY HIGH -- rapid altitude loss
    At t=30.0 s the aircraft lost 15.0 m in 2.0 s (7.5 m/s),
    descending from 50.0 m to 34.9 m (bottomed out at t=32.0 s).

ASSESSMENT
----------------------------------------------------------------
1 altitude anomaly flagged for review; highest severity: HIGH.
================================================================
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
  report.py         Plain-language incident report: folds structure + drop events
                    into overview / flight summary / findings / assessment, with a
                    severity grade per finding. Pure formatting, stdlib only.
  main.py           One-command: generate -> parse -> detect -> report.
tests/              pytest: bag contents + parser structure + injected-drop check
                    + detector (finds the anomaly, rejects climbs/flat/gentle)
                    + report (sections present, anomaly + nominal, severity bands).
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

### How the incident report works

`report.py` is **pure formatting** — it derives nothing about the flight that the
parser and detector did not already establish, which keeps it honest and easy to
test. It folds the `BagStructure` and the list of drop events into four sections:
overview (source, flight time, channels + rates), flight summary (altitude
profile), findings (each drop in plain English), and a one-line assessment.

**Severity grade — "Decisions to sanity-check"** (assumption, *not* a standard):
each drop is graded `HIGH` (≥ 10 m **or** ≥ 5 m/s), `MODERATE` (≥ 5 m or ≥ 2 m/s,
i.e. it cleared the detector), else `LOW`. First-pass guesses for a small UAV,
chosen so the synthetic ~15 m / ~7.5 m/s anomaly reads as `HIGH`. Tune per airframe.

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
