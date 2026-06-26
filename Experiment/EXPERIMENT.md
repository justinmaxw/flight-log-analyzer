# EXPERIMENT.md — The Killer Experiment (does reliable causal RCA = moat or feature?)

*Run this before committing to the company. It is pre-registered: the pass/fail
bars are fixed BEFORE looking at results, so we can't rationalize a yes.*

---

## The one question
On flight logs the system has **never seen**, can it produce a **correct causal
chain** AND **correctly abstain when evidence is thin** — with a **near-zero
confident-wrong rate** — and does getting there **require a real harness**, or
does a naive LLM already do it?

- If a real harness is required to be reliable → **reliability is hard → moat → company.**
- If a naive LLM already nails it → **it's a feature → platforms absorb it → walk** (keep the analyzer as a portfolio/hiring artifact).
- If even the harness can't be made reliable without per-log hand-tuning → **not trustworthy → walk** (it's consulting in a product costume).

## The core design — 3 arms (this is what measures the moat)
Run the SAME logs through three systems and compare. The point isn't "does mine
work," it's "where does reliability come from, and is that part absorbable."

- **Arm 1 — Naive.** Dump a large chunk of the decoded log into an off-the-shelf
  LLM with a good prompt. No detectors, no abstention. *This is what a platform
  bolts on in a quarter.*
- **Arm 2 — Slices only.** Deterministic detectors → event correlation → feed the
  model only a tight, structured slice. No grounding/abstention discipline.
- **Arm 3 — Full harness.** Arm 2 + every causal claim must cite a signal+timestamp
  (grounding) + ranked-candidate abstention logic (below).

Reading the result:
- Arm 1 ≈ Arm 3, both good → **feature.** It was always easy. Walk.
- Arm 2 ≈ Arm 3, both ≫ Arm 1 → moat is "good slicing" — real but **partly absorbable** (platforms have the data to slice too).
- Arm 3 ≫ Arm 2 ≫ Arm 1 → moat is the **grounding + abstention layer** — the hardest part to absorb. **Strongest company signal.**

## Test corpus — 3 buckets (~25–35 logs total for a v0 read)
Deliberately small. Enough to see a signal, not a paper. Pick **one failure
domain** to go deep (recommend: GPS-denied / EKF estimator divergence, or
vibration-induced instability — both have rich public examples).

- **A. Determinate (~15–20):** one clear, expert-confirmed root cause. Tests accuracy.
- **B. Under-determined (~5–8):** genuinely ambiguous — multiple plausible causes,
  or the smoking gun wasn't logged. Tests abstention. The system should NOT
  confidently pick one.
- **C. Nominal (~5):** no real fault. Tests hallucination. Should say "nominal."

**Sourcing labeled data:** `review.px4.io` hosts thousands of public ULogs;
PX4/ArduPilot community forum threads often pair a log with a dev- or
consensus-confirmed diagnosis = free ground truth. Prefer threads where a core
dev or strong consensus confirmed the cause.

## ⚠️ The threat that can invalidate everything — training-data contamination
Public forum crashes may be **in the model's training data** (Roboto's own demo
used a public forum crash). If the model "recognizes" the log, it recites the
answer without reasoning — inflating BOTH arms and faking a moat (or faking
"easy"). Mitigate, in order of strength:
1. Use a few of **your own freshly-captured or design-partner logs** with known causes (gold standard — zero contamination).
2. Prefer logs newer than the model's training cutoff.
3. Strip/alter identifying metadata + never paste the forum text into the prompt.
4. Sanity check: perturb a log (rename vehicle, shift timestamps). If the answer
   survives perturbation it's reasoning; if it collapses, it was recall.

## "Correct cause" rubric (decide this before scoring)
Causal chains have depth (e.g., *vibration → accel clipping → EKF rejects accel →
estimator divergence → position error → crash*). Grade the **initiating cause +
mechanism**, not a downstream symptom.

- **Correct** = right root cause AND right mechanism/chain.
- **Partial** = right symptom but wrong/missing root, OR right root but wrong mechanism.
- **Wrong** = asserts an incorrect root cause.
- **Abstained** = declined / returned honest ranked candidates.

Use two graders where possible (you + the documented dev diagnosis) to cut
subjectivity.

## Abstention mechanism (the differentiator — design it as output, not a flag)
Don't output one answer. Output **ranked candidate causes, each with its
supporting signals + a confidence**, and a **commit threshold**:
- Top candidate clears threshold with corroborating evidence → commit to it.
- Nothing clears threshold / top candidates tie → **abstain** ("insufficient
  evidence; candidates: X, Y") rather than guess.
Test gates worth trying: require N independent corroborating signals per cause;
self-consistency (re-run; if causes disagree, downgrade); detector-anchoring
(only assert causes traceable to a deterministic detector hit + plausible mechanism).

## Metrics (confident-wrong is the star)
1. **Confident-Wrong Rate (CWR)** — fraction of ALL logs where it commits, high-
   confidence, to a wrong cause. **Target ≈ 0.** The single most important number;
   in a safety context a confident wrong answer is worse than silence.
2. **Root-cause accuracy** on bucket A (Correct% / Partial%).
3. **Abstention quality** on B + C (fraction correctly abstained / called nominal).
4. **Grounding rate** — % of causal claims with a verifiable signal+timestamp.
   *Ungrounded = fail even if the conclusion is right* (can't trust or sell it).
5. **Lift over baseline** — Δ(CWR, accuracy) across the three arms. ← the moat.
6. *(secondary)* time-to-answer vs. a human doing the same trace.

## Pre-registered verdict (lock these numbers BEFORE running; adjust now, not after)
Starting thresholds — **assumptions, tune once, then freeze:**
- **MOAT → pursue company:** Arm 3 reaches **CWR ≤ 5%**, **Correct ≥ 70%** (bucket A),
  **abstention quality ≥ 80%** (B+C) — AND the naive Arm 1 is materially worse
  (e.g., **Arm 1 CWR ≥ 25%**: it confidently bullshits and the harness is what fixes it).
- **FEATURE → walk to portfolio:** Arm 1 ≈ Arm 3 and both decent. Reliability was easy.
- **NOT-TRUSTWORTHY → walk:** No arm gets CWR low without per-log hand-tuning.

## Protocol (run order)
1. Lock the rubric + thresholds above (Strategy mode, with Justin).
2. Assemble the corpus (buckets A/B/C); record ground-truth + source for each.
3. Build Arm 1 (naive) first — fastest, and it's the bar to beat.
4. Build Arm 2 (port v0 detectors + correlation → slice).
5. Add Arm 3 (grounding + abstention).
6. Run each arm on all logs. **Re-run 5×** for stability (per project DoD: report
   the concrete observed output, never "should work").
7. Score, fill the metrics table, read against the pre-registered verdict.
8. Write the honest result — including if it says walk.

## Threats to validity (name them in the writeup)
- Ground-truth quality (forum diagnoses can be wrong) → prefer dev-confirmed.
- Contamination (above) → the biggest one.
- Single-domain overfit (nailing one class ≠ general) → fine for v0; vertical-deep is the strategy anyway.
- "Correct cause" subjectivity → rubric + second grader.

## Why this is the highest-EV thing to build regardless
- Result = MOAT → you have a defensible company thesis and the eval set is the
  seed of your flywheel (verified causal chains).
- Result = FEATURE/WALK → you have the best portfolio artifact a Sift / Roboto /
  Anduril interviewer will see: *"here's exactly where current models break on
  real flight logs, and here's the abstention design I built to catch it."*
You cannot run this and come out empty-handed.
