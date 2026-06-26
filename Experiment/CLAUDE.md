# CLAUDE.md — experiment/ (GPS-denied / EKF-divergence killer experiment)

## Precedence (read first)
This folder runs a self-contained experiment. The parent-directory `CLAUDE.md`
governs the original ROS2-bag analyzer codebase — it does NOT govern this work.
For anything in `experiment/`, the governing docs are, in order:
`PRE-REGISTRATION.md` (frozen, wins on metrics/rubric) → `EXPERIMENT.md` (protocol)
→ `RUNBOOK-gps-ekf.md` (setup specifics) → `PROJECT.md` (charter/scope). If the
parent CLAUDE.md or anything here conflict, STOP and ask which wins. Do not import
the old project's company-mode framing.

## Mode
**BUILD.** Loop build → run → read-error → fix → re-run → test without per-step
approval, within the rules below.

## Scope for THIS session — Milestone 1 ONLY
**Goal:** prove that `failure gps off` produces an EKF-divergence signature in a
real ULog on this machine. Nothing more. Do NOT build Arm 1, do NOT generate the
full corpus, do NOT start scoring.

**Steps (see RUNBOOK Stage 1–2 for detail):**
1. Get PX4 SITL running. Prefer a path that works on this machine: try **SIH**
   (headless, zero-dep) first; if `failure gps off` returns "unsupported" under
   SIH, fall back to **jMAVSim** (GPS-off injection is confirmed there). Gazebo is
   not needed for this domain.
2. Take off, fly ~20–30s in position control.
3. `param set SYS_FAILURE_EN 1`, record the sim time T, then `failure gps off`.
   Let the failsafe play out, then save the `.ulg`.
4. Inspect with `pyulog` (`ulog_info`): confirm GPS dropout, estimator
   innovations / test-ratios climbing, a "no global position" failsafe event, and
   the position estimate diverging. Confirm the EXACT topic/field names from the
   file (names vary by PX4 version — don't trust remembered names).

**Definition of Done:** point at the actual `.ulg` and state the concrete observed
output — "GPS cut at t=T; topics X/Y show innovations climbing; failsafe Z fired;
position diverged." Never "should work."

## Hard rules
- **Installs require approval.** PX4 toolchain, `MAVSDK`, `pyulog`, sim deps,
  Java/JDK — name the package + why, then WAIT for "go." Do not auto-install.
- **Escalate, don't stall** on: any out-of-allowlist/irreversible action; a
  contradictory decision with no safe default; or 3 distinct failed fixes on the
  same chunk.
- **No fabrication.** State only what was actually run + observed. Never invent a
  topic name, a metric, or a result. If a step wasn't run, say so.
- Keep a scripted, reproducible path where possible (a fixed mission + scripted
  inject via the MAVSDK failure plugin) — but only after the manual inject in
  step 3 is confirmed once.

## Checkpoint at the end (≤150 words, phone-readable)
Works / Verified by (how tested + actual observed output) / Decisions to
sanity-check / Commit / Next. Then STOP for review before milestone 2.
