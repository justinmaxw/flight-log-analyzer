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
| **M4** | IMU-spike detector + run any bag | ✅ done |
| M5 | *(stretch)* Simple UI / CV angle | |

## Quick start

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install rosbags pytest

# One command — analyze any rosbag2 bag and print the incident report:
./.venv/bin/python src/main.py path/to/bag_dir

# No path → generate the synthetic demo bag, then analyze it:
./.venv/bin/python src/main.py

# Individual stages also run standalone on any bag:
./.venv/bin/python src/parser.py       path/to/bag_dir   # structure
./.venv/bin/python src/detector.py     path/to/bag_dir --min-drop 5 --min-rate 2
./.venv/bin/python src/imu_detector.py path/to/bag_dir --min-dev 5
./.venv/bin/python src/report.py       path/to/bag_dir   # full report

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
IMU acceleration held near 9.8 m/s^2 baseline (peak 41.2 m/s^2) across 3000 samples.

FINDINGS
----------------------------------------------------------------
2 anomalies flagged:

[1] SEVERITY HIGH -- rapid altitude loss
    At t=30.0 s the aircraft lost 15.0 m in 2.0 s (7.5 m/s),
    descending from 50.0 m to 34.9 m (bottomed out at t=32.0 s).

[2] SEVERITY HIGH -- IMU acceleration spike
    At t=45.0 s acceleration spiked to 41.2 m/s^2,
    +31.4 m/s^2 above the 9.8 m/s^2 baseline (held 0.08 s).

ASSESSMENT
----------------------------------------------------------------
2 anomalies flagged for review; highest severity: HIGH.
================================================================
```

## Architecture

```
src/
  generate_bag.py   Writes a deterministic synthetic rosbag2 bag with two injected
                    anomalies (altitude drop + IMU jolt) as detector ground truth.
  parser.py         Type-agnostic structural reader: topics, msg types, counts,
                    duration, start/end; extracts altitude (PoseStamped) and
                    IMU accel-magnitude (Imu) signal series in one pass.
  detector.py       Altitude-drop detector: bounded-lookback descent scan over the
                    altitude series -> rapid-loss events (drop, rate, peak->trough).
  imu_detector.py   IMU-spike detector: robust-baseline (median/MAD) deviation scan
                    over the accel series -> acceleration-spike events.
  report.py         Plain-language incident report: folds structure + both event
                    lists into overview / flight summary / findings / assessment,
                    with a severity grade per finding. Pure formatting, stdlib only.
  main.py           One command: analyze any bag (or generate the demo) end-to-end.
tests/              pytest (31): bag contents + parser structure + injected
                    drop/spike checks + both detectors (find the anomalies, reject
                    benign signals) + report (sections, severity) + one-command run.
```

The parser separates **structure** (works on any bag, no deserialization) from
**signal extraction** (altitude + IMU series), so detectors layer on top without
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

### How the IMU-spike detector works

`imu_detector.py` scans the linear-acceleration magnitude series for brief spikes
(a jolt, impact, or sensor saturation). The baseline is the **median** of the
series and the spread is the **median absolute deviation (MAD)** — both robust, so
a short, large spike barely moves them and the baseline stays near the true
resting value (~9.81 m/s², gravity) instead of being dragged up by the very event
we want to catch. That is the classic failure of a mean/standard-deviation
threshold. A sample is flagged when its deviation above baseline clears **both** an
absolute floor (`min_dev_mps2`, 5 m/s²) and a robust multiple (`k_mad`·1.4826·MAD,
default 6σ); consecutive flagged samples form one event, reported at its peak.

**Detector thresholds — "Decisions to sanity-check"** (assumptions, tunable via
CLI): `min_dev_mps2=5`, `k_mad=6`. The injected ~31 m/s² jolt clears these with
huge margin while small noise does not. Real thresholds depend on the airframe and
IMU placement.

### How the incident report works

`report.py` is **pure formatting** — it derives nothing about the flight that the
parser and detectors did not already establish, which keeps it honest and easy to
test. It folds the `BagStructure` and both event lists (altitude drops + IMU
spikes) into four sections: overview (source, flight time, channels + rates),
flight summary (altitude profile + IMU baseline), findings (each anomaly in plain
English), and a one-line assessment counting findings and the worst severity.

**Severity grade — "Decisions to sanity-check"** (assumption, *not* a standard):
an altitude drop is `HIGH` (≥ 10 m **or** ≥ 5 m/s), `MODERATE` (≥ 5 m or ≥ 2 m/s),
else `LOW`; an IMU spike is `HIGH` (≥ 20 m/s² ≈ 2 g above baseline), `MODERATE`
(≥ 5 m/s²), else `LOW`. First-pass guesses for a small UAV, chosen so both
synthetic anomalies read as `HIGH`. Tune per airframe.

## Synthetic bag schema — "Decisions to sanity-check"

These are **documented standard ROS2 choices**, not invented, but a domain
reviewer should confirm they match the real systems you care about:

| Choice | Value | Note |
|---|---|---|
| Pose topic / type | `/flight/pose` · `geometry_msgs/msg/PoseStamped` | altitude = `pose.position.z` (meters) |
| IMU topic / type | `/flight/imu` · `sensor_msgs/msg/Imu` | `linear_acceleration` m/s², `angular_velocity` rad/s |
| Rates / duration | pose 10 Hz, IMU 50 Hz, ~60 s | → 600 + 3000 = 3600 messages |
| Injected anomaly 1 | ~15 m altitude drop over ~2 s at t≈30 s, partial recovery | M2 detects this |
| Injected anomaly 2 | ~40 m/s² +x acceleration jolt for ~0.1 s at t≈45 s | M4 detects this |
| IMU convention | gravity on +z (≈9.81); `orientation_covariance[0] = -1` | REP-145 "no orientation estimate" |

Real PX4/MAVROS stacks often publish on names like `/mavros/local_position/pose`
and `/mavros/imu/data` — topic names are configurable, which is why the parser is
generic rather than hard-coded to these.
