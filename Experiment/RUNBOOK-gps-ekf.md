# RUNBOOK — GPS-denied / EKF-divergence experiment (operational walkthrough)

*Specializes `EXPERIMENT.md` (the protocol) to the locked failure domain. Setup
facts here are verified against PX4 docs (mid-2026); every nontrivial claim is
tagged verified/assumption. If this conflicts with EXPERIMENT.md, EXPERIMENT.md
wins on protocol; this file wins on GPS/EKF specifics.*

---

## Stage 0 — Lock the pre-registration FIRST (not started yet)
**Nothing below gets built until the rubric + thresholds are frozen with Justin.**
This is the next STRATEGY decision, still open. EXPERIMENT.md's proposed defaults
(to confirm or adjust, then freeze and date):
- MOAT/strong-artifact bar: Arm 3 CWR ≤ 5%, Correct ≥ 70% (bucket A), abstention
  quality ≥ 80% (B+C), AND Arm 1 CWR ≥ 25%.
- "Correct cause" = right **initiating cause + mechanism**, graded on the chain
  (GPS loss → innovation/test-ratio growth → EKF rejects/resets → position error
  → failsafe), not a downstream symptom.

Do this before touching a simulator so results can't bend the bars.

---

## Why this domain de-risks the #1 threat (state this in the writeup)
EXPERIMENT.md's biggest threat-to-validity is **training-data contamination** — the
model reciting a memorized forum crash instead of reasoning. SITL-generated logs
are **contamination-free by construction**: you inject the fault, so you own the
ground truth and timestamp, and the log never existed before you made it. For
buckets A and C this largely *neutralizes* the contamination threat rather than
just mitigating it — the strongest methodological argument for this domain.

The counter-threat it introduces — **"does nailing synthetic GPS-loss generalize
to real flights?"** — is handled by including a small held-out slice of *real*
public GPS-loss logs (below). Name both honestly.

---

## Stage 1 — Environment (verified setup)
The old "SITL on macOS arm64 is painful" assumption is **partly outdated**.

- **Native Apple Silicon is now PX4-dev-team supported.** *Verified (source: PX4
  Guide, macOS Development Environment — "works on both Intel and Apple Silicon
  Macs… supported by the PX4 dev team").* The historical pain was **Gazebo** on
  arm64, not the PX4 build itself.
- **Recommended simulator: jMAVSim** for corpus generation. Reason: GPS-failure
  injection is *confirmed working* under jMAVSim in PX4's own issue tracker
  (`make px4_sitl jmavsim` → `failure gps off` triggers the no-global-position
  failsafe). *Verified (source: PX4-Autopilot issues #15065, #15066).* It runs on
  macOS with Homebrew OpenJDK 17+, and runs in **lockstep** (PX4 and sim locked to
  the same clock) — which gives you deterministic, repeatable runs, exactly what
  the "re-run 5× for stability" step needs. *Verified (source: PX4 Guide, jMAVSim
  / Simulation).*
- **SIH** (Simulation-In-Hardware: a lightweight physics sim built into PX4, zero
  external deps, headless) is the docs' explicit macOS recommendation and would be
  ideal — BUT whether the `failure gps off` injection works under SIH is **not
  confirmed** in the docs (failure injection is documented as simulator-dependent;
  see caveat below). *Assumption — test SIH first; if `failure gps` returns
  "unsupported," fall back to jMAVSim.*
- **Docker fallback:** pre-built SITL containers (`px4io/px4-sitl`) publish
  **arm64** images — a zero-build escape hatch if the native toolchain fights you.
  *Verified (source: PX4 Guide, Pre-built SITL Packages).*

⚠️ **The caveat that shapes everything:** failure injection "requires support in
the simulator… many failure types are not broadly implemented" and is documented
as supported in **Gazebo Classic**. *Verified (source: PX4 Guide, System Failure
Injection.)* GPS-off specifically is confirmed on jMAVSim (issues above), so
jMAVSim is the safe default — but **smoke-test the inject before building 20 logs
on top of it.** First milestone is literally "prove `failure gps off` produces an
EKF-divergence signature in a ULog on my machine."

> Package installs (`pyulog`, `MAVSDK`, the sim toolchain) are on the BUILD deny
> list — they'll hit escalation. That's correct; name the package + why, wait for
> "go."

---

## Stage 2 — Corpus generation (buckets A / B / C)
Target ~25–35 logs total. Map each bucket to GPS/EKF deliberately.

**The injection primitive (verified, source: PX4 issues #15065/#15066 + failsafes
doc):**
```
pxh> param set SYS_FAILURE_EN 1     # arm the failure-injection system
pxh> failure gps off                # cut all GPS at a known sim time → log it
pxh> failure gps ok                 # restore (for intermittent-loss cases)
```
The same is scriptable via the **MAVSDK failure plugin** (a direct mapping of the
`failure` command; it's what PX4's own integration tests use). *Verified (source:
PX4 Guide, System Failure Injection.)* **Script it through MAVSDK** — that turns
corpus generation into a reproducible harness (a fixed mission + a scripted inject
at t=T), which is itself a credibility win for the artifact.

- **Bucket A — determinate (~15–20).** Clean "GPS lost at known T → EKF
  divergence." Vary across logs so it's not one scenario 18 times: altitude,
  flight mode (POSCTL vs AUTO/mission), time-to-loss, full dropout vs
  intermittent (`off`→`ok`→`off`). Ground truth is **exact by construction** (you
  hold T and the cause). This is your accuracy bucket.
- **Bucket B — under-determined (~5–8).** Genuine ambiguity, where the system
  should *abstain or return ranked candidates*, not guess. Two ways, with a
  tradeoff to decide:
  - *Synthetic ambiguity:* co-inject a second plausible contributor (e.g.
    `failure mag off` alongside marginal GPS) so no single smoking gun dominates.
    Caveat: non-GPS failure types may be "unsupported" under your sim — **verify
    each inject works before relying on it.** *(Assumption.)*
  - *Real ambiguous logs:* curate a few public forum logs where the dev thread
    itself shows real uncertainty. Strength: ambiguity is authentic. Cost: these
    carry contamination risk → **perturbation-check them** (below).
  - *Likely best:* lean real logs for B (authentic ambiguity), keep SITL for A/C.
- **Bucket C — nominal (~5).** Clean flights, no inject. Tests hallucination — the
  system must say "nominal," not invent a fault.

**Plus a generalization slice (~3–5 real GPS-loss logs)** from review.px4.io /
forum threads with a **dev-confirmed** GPS-loss diagnosis. These test whether
synthetic competence transfers to real flights. Perturbation-check every one.

**Per-log metadata to record:** bucket, ground-truth cause + mechanism, injection
time T (if synthetic), source, and **contamination status** (synthetic = none;
real = "perturbation-checked: survived/collapsed").

**Perturbation check (mandatory on every real log):** rename the vehicle, shift
timestamps, then re-run. If the model's answer survives → reasoning. If it
collapses → it was recall; flag and quarantine. *(This is your recall detector.)*

---

## Stage 3 — Signals for grounding (what Arm 2's detectors key off)
*EKF = the Extended Kalman Filter, PX4's estimator that fuses GPS/IMU/baro/mag into
one best-guess of position & velocity. An "innovation" is the gap between what a
sensor reports and what the filter predicted; when GPS innovations and their
**test ratios** blow past threshold, the filter rejects GPS and the position
estimate diverges.* That divergence chain is what you're grounding claims against.

Signal families to anchor on (confirm the **exact** current ULog topic/field names
on your own logs with `pyulog`'s `ulog_info` — names have changed across PX4
versions, so don't trust a name you didn't read out of your file):
- GPS input: `sensor_gps` / `vehicle_gps_position` (satellites, fix type, dropout).
- Estimator health: `estimator_status` / `estimator_status_flags`,
  `estimator_innovations` + `estimator_innovation_test_ratios`,
  `estimator_event_flags` (GPS-check fail, reset events).
- Outcome: `vehicle_local_position` / `vehicle_global_position` validity flags,
  `vehicle_status` / failsafe flags, plus the EKF console events in the log
  (`no global position`, GPS-fusion stop/reset).

Your existing ROS2-bag detectors (altitude-drop, IMU-spike) port here as
**GPS-dropout** + **innovation-divergence** detectors → that's the Arm 2 work.

---

## Stage 4 — Build the three arms (keep them clean)
Build cheapest-first; the *gap between arms is the measurement*, so no harness
logic may leak left.
1. **Arm 1 — naive.** Decode the ULog to text, dump a large slice into an
   off-the-shelf LLM with a good prompt. No detectors, no abstention. The bar to
   beat.
2. **Arm 2 — slices.** Run detectors → correlate into a causal window → feed the
   model only that tight structured slice. No grounding/abstention discipline.
3. **Arm 3 — full harness.** Arm 2 + every causal claim must cite a
   signal+timestamp (grounding) + ranked-candidate abstention with a commit
   threshold (commit only if top candidate clears threshold with corroboration;
   else "insufficient evidence; candidates X, Y").

---

## Stage 5 — Scoring harness
- **Grader independence:** the model that produced an answer does **not** grade
  itself. Score against recorded ground truth + Justin; or a separate judging step
  that is *given* the ground truth. Two graders where possible.
- **Metrics (CWR is the star):** Confident-Wrong Rate (commits, high-confidence,
  to a wrong cause — target ≈ 0); root-cause accuracy on A; abstention quality on
  B+C (abstention scores as **correct**); grounding rate (% claims with a
  verifiable signal+timestamp — ungrounded = fail even if right); lift across arms.

---

## Stage 6 — Run, read, write
1. Run each arm on all logs; **re-run 5×** for stability; report the concrete
   observed numbers (never "should work").
2. Fill the metrics table; read against the **frozen** verdict from Stage 0.
3. Write the honest result — including if it says "feature/walk." Include the
   threats section: synthetic-realism, single-domain scope, ground-truth quality,
   "correct cause" subjectivity.

---

## First three milestones (smallest credible path)
1. **Prove the inject.** One jMAVSim flight, `failure gps off` at known T, confirm
   the ULog shows the EKF-divergence signature. (De-risks Stage 1's caveat.)
2. **Generate bucket A + C** via a scripted MAVSDK mission + inject; label them.
3. **Build Arm 1** and run it on A+C. Fastest signal on whether this is even hard.

Stop and checkpoint at each boundary (Works / Verified by / Sanity-check / Commit /
Next). Resist scope creep: 25–35 logs, honest + reproducible, then write it.
