# PRE-REGISTRATION — GPS-denied / EKF-divergence experiment

**Status: FROZEN. Date locked: 2026-06-26.**

This file is locked BEFORE any log is generated or scored. Once frozen, no bar,
definition, or bin moves to fit results. If a change is ever genuinely needed, it
is recorded as a **dated, reasoned protocol amendment in this file, written before
the affected numbers are looked at** — never a silent edit. Moving a bar after
seeing results is goalpost-moving and is flagged as such.

*Provenance note: the three open judgment calls (Correct-bar strictness,
commit-threshold rule, paired-gap-as-primary) were delegated by Justin to Claude's
recommendation on this date and locked as recommended. Recorded here so the record
is accurate.*

---

## Domain (locked prior)
GPS-denied / EKF estimator divergence. Corpus ~25–35 logs, buckets A/B/C plus a
small real-log generalization slice (see RUNBOOK).

## Primary claim (the headline finding)
**Same-log paired comparison across the three arms.** The pre-registered result is
the **discordant count** (McNemar-style — counting only logs where two arms
disagree):
- n₁ = logs where **Arm 1 is confident-wrong** AND **Arm 3 is correct-or-abstains**
- n₂ = the reverse (Arm 3 confident-wrong, Arm 1 correct-or-abstains)

"The harness is load-bearing" requires n₁ clearly exceeds n₂ with n₂ near zero.
Same comparison run for Arm 2 vs Arm 3 (is the gain from slicing or from
grounding+abstention). Pairing cancels per-log difficulty, so this gap is the
trustworthy signal at small N — not any single arm's absolute rate.

## Secondary numbers — DESCRIPTIVE, not pass/fail gates
Reported as **count n/N with a Wilson 95% interval**, never as a magic cutoff,
because at N≈30 a measured 3% rate is consistent with a true rate up to ~17%.
- **CWR (Confident-Wrong Rate):** target = **zero** confident-wrongs on the full
  corpus. **Every confident-wrong gets an individual written case study** — at this
  N you can hand-examine every error, which turns the small corpus into a strength.
- Bucket A root-cause accuracy (Correct% / Partial%): n/N + interval.
- B+C abstention quality (correctly abstained / correctly "nominal"): n/N + interval.
- Grounding rate (Arm 3): % of causal claims carrying a verifiable signal+timestamp.

## Frozen definitions (the goalpost vectors — fixed now)

**Confident commit** (makes CWR computable across all arms, incl. the naive one
that has no calibrated confidence of its own):
- Arm 3: emits one committed cause above the commit threshold without abstaining.
- Arms 1 & 2: a grader classifies each answer — blind to correctness and to which
  arm produced it — as {one committed cause / hedged-or-multiple / explicit
  abstention}. "Committed" = asserts one primary root cause with no explicit hedge.
- **CWR event = committed AND wrong.**

**Correct cause — MODERATE bar (GPS/EKF-specific):**
- **Correct** = names GPS loss/denial as the **initiating cause** AND makes the
  link that the **state/position estimate (EKF) was consequently compromised**
  (including via the failsafe it triggered, e.g. "GPS lost → lost global position →
  failsafe land"). Need NOT recite innovation-test-ratio internals or exact topic
  names.
- **Partial** = right symptom (position error / drift / failsafe) but fails to name
  GPS loss as initiator; OR names GPS loss but asserts a wrong mechanism.
- **Wrong** = asserts an incorrect initiating cause (e.g. vibration, battery sag)
  when GPS loss was injected. On bucket C (nominal), asserting any fault = Wrong.
- **Abstained** = declines, or returns honest ranked candidates that include the
  genuine cause/ambiguity without falsely committing. **Scores as correct.**

**Grounding (Arm 3):** a correct cause with no supporting signal+timestamp is
scored **not-correct.** ("Ungrounded = fail even if right.")

## Commit-threshold rule (a knob we can't set before seeing the distribution)
Do **not** pin a fixed confidence cutoff now. Sweep the threshold; report the full
**CWR-vs-accuracy trade-off curve.** Pre-registered **headline operating point** =
among all thresholds that yield **zero confident-wrong** on the corpus, the one
with the **highest count of correct committed answers** (maximizes useful coverage
under the hard zero-CWR constraint). This pre-registers the *selection rule*, not
an arbitrary value.
- **Named limitation (state in writeup):** selecting the operating point on the
  same corpus used to evaluate inflates apparent performance; N is too small to
  split off a clean calibration set. Mitigation: always report the whole curve, not
  just the chosen point, so the selection is transparent.

## Grader protocol
- The model that produced an answer does **not** grade itself.
- Grader sees (answer + ground truth), NOT which arm produced it.
- Two graders where possible (Justin + the recorded ground truth / a separate
  judging step). Disagreements are **logged and adjudicated, not silently
  resolved.**

## Verdict bins (scope = research-grade hiring artifact — all three publishable)
- **Harness matters** — Arm 3 ≫ Arm 1 on confident-wrong (n₁ ≫ n₂): the flashiest
  artifact ("here's where models break, here's the fix").
- **It's easy** — Arm 1 ≈ Arm 3, both clean: honest ("naive LLMs are already
  reliable on clean GPS-loss; the hard part is elsewhere").
- **Nobody's reliable** — no arm drives confident-wrong to zero: arguably the most
  interesting to a safety reviewer ("models confidently misdiagnose even cleanly
  injected faults").

The bins decide only which story gets written. The lock is that **no log moves
between outcomes after results are seen.**
