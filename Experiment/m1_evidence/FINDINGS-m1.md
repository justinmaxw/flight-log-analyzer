# Milestone 1 — Findings: `failure gps off` produces an EKF-divergence signature

**Status: DONE & VERIFIED.** Date: 2026-06-26.

**Goal (RUNBOOK Stage 1–2 / folder CLAUDE.md):** prove that `failure gps off`
produces an EKF-divergence signature in a real ULog on this machine. Nothing more.

## Setup actually used (verified)
- **Simulator: SIH** (Simulation-In-Hardware, headless, zero external deps),
  airframe `sihsim_quadx`. Run via `make px4_sitl sihsim_quadx`, `HEADLESS=1`.
- **SIH supports GPS-off injection** — this resolves the open assumption in
  RUNBOOK Stage 1 (which said SIH support for `failure gps off` was *unconfirmed*,
  jMAVSim the safe fallback). **No jMAVSim / Java-17 / ant needed.**
  Observed in the run log: `WARN [failure] inject failure unit: gps (4),
  type: off (1)` → `INFO [sensor_gps_sim] CMD_INJECT_FAILURE, GPS 1 off / GPS 2 off`.
- PX4 `main` @ `8184116` (shallow clone), built with Apple clang on arm64.
- Inspected with `pyulog` 1.2.3.
- Inject was **manual via the pxh console** (timed stdin driver), per CLAUDE.md
  ("script via MAVSDK only after the manual inject is confirmed once").

## Flight timeline (sim time, from the ULog event stream)
| t (s) | event |
|------:|-------|
| 18 | armed, takeoff (default 2.5 m) |
| 20 | takeoff detected — ~25 s position-control flight |
| **43** | **`failure gps off` injected (T)** — GPS 1 & 2 off |
| 48 | `Failsafe activated: switching to Descend` / `mc_pos_control: Failsafe: blind land` |
| 50 | `GNSS data fusion stopped` (estimator drops GPS) |
| 54 | landing detected |
| 56 | disarmed by landing |

## The EKF-divergence signature (concrete observed output)
Exact topic/field names **read from this file** (PX4 names drift across versions):

1. **GPS dropout** — `sensor_gps`: last sample at **t=42.85 s**, **0 samples after
   inject**. The GPS stream stops dead at T. (`vehicle_gps_position.fix_type`
   stays `3` only because the topic holds its last value — the real dropout is the
   stream stopping, not a fix-type change.)
2. **Estimator stops fusing GPS** — event `GNSS data fusion stopped` (t=50);
   `estimator_status.control_mode_flags` GPS bits drop.
3. **Position estimate invalidated** — `vehicle_local_position.xy_valid` and
   `v_xy_valid` flip **1 → 0 at t=48 s**.
4. **Estimate diverges (the headline)** — true horizontal error
   `|estimate − groundtruth|` (`vehicle_local_position` vs
   `vehicle_local_position_groundtruth`): 0.14 m @ T → 3.35 m (t49) → 11.4 m (t55)
   → **peak 18.9 m**. Filter's own reported uncertainty `eph` tracks it:
   0.28 m → **9.0 m**. The EKF dead-reckons away from truth *and knows it*.
5. **Failsafe** — `Failsafe activated … switching to Descend` (the
   no-global-position failsafe) → blind land.

## Decisions to sanity-check (for a beginner / for Arm-2 design)
- **GPS-*off* signature = fusion STOPS, not innovations CLIMB.** RUNBOOK/PRE-REG
  list "innovations / test-ratios climbing" as an expected signal — that is the
  signature of *corrupted/biased* GPS. For a clean GPS **removal**, the GPS
  innovation test ratios *freeze/go stale* (no new GPS innovations) and the
  divergence shows in **outcome** signals: `xy_valid→0`, `eph↑`, true-error↑,
  `GNSS data fusion stopped`. → The Arm-2 GPS-dropout detector should key on
  **stream-stop + xy_valid/eph growth**, not on rising GPS innovation ratios.
  (Bucket B's *intermittent/marginal* GPS may yet show climbing ratios — worth a
  later check.)
- `estimator_status.gps_check_fail_flags` stayed `0` — GPS didn't fail a quality
  gate, it simply vanished. Consistent with the above.
- T=43 s inject time is set by the fixed driver timeline (22 s boot + ~25 s flight).

## Reproduce
```
# build once:  cd ~/PX4-Autopilot && make px4_sitl_default   (venv on PATH)
bash run_gps_inject.sh                       # flies, injects at T, saves .ulg
.venv/bin/python ulg_inspect.py  <file.ulg>  # topic names + signature table
.venv/bin/python ulg_inspect2.py <file.ulg>  # dropout timing + true divergence
```
