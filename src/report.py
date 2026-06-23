"""Plain-language incident report generator (Milestones 3-4).

Turns the machine-readable outputs of the earlier milestones --
``BagStructure`` (M1 parser), a list of ``AltitudeDropEvent`` (M2 detector) and a
list of ``ImuSpikeEvent`` (M4 detector) -- into a single human-readable incident
report a non-engineer can skim:

  1. OVERVIEW    -- what the log is (source, flight time, data channels).
  2. FLIGHT      -- what happened (altitude profile, IMU baseline, data rates).
  3. FINDINGS    -- what looked anomalous, in plain English, with severity.
  4. ASSESSMENT  -- one-line verdict (nominal vs. N items flagged for review).

This module is pure formatting: it computes nothing about the flight that the
parser/detectors did not already establish, so it stays honest and testable.
Stdlib only -- no new dependencies.

Severity heuristic (ASSUMPTION -- flagged for sanity-check, not a standard):
  Altitude drop, graded on magnitude or rate, whichever is worse:
    HIGH      drop >= 10 m  OR  rate >= 5.0 m/s
    MODERATE  drop >=  5 m  OR  rate >= 2.0 m/s   (i.e. cleared the detector)
    LOW       anything else that was still flagged
  IMU spike, graded on acceleration deviation above baseline:
    HIGH      dev >= 20 m/s^2  (~2 g)
    MODERATE  dev >=  5 m/s^2  (i.e. cleared the detector)
    LOW       anything else that was still flagged
  First-pass engineering guesses for a small UAV, chosen so the synthetic
  anomalies (~15 m / ~7.5 m/s drop; ~31 m/s^2 jolt) read as HIGH. Revisit on
  real logs.
"""
from __future__ import annotations

from dataclasses import dataclass

# Severity band thresholds (ASSUMPTION -- see module docstring).
SEV_HIGH_DROP_M = 10.0
SEV_HIGH_RATE_MPS = 5.0
SEV_MODERATE_DROP_M = 5.0
SEV_MODERATE_RATE_MPS = 2.0
SEV_HIGH_IMU_DEV_MPS2 = 20.0
SEV_MODERATE_IMU_DEV_MPS2 = 5.0

_SEV_ORDER = {"HIGH": 3, "MODERATE": 2, "LOW": 1}


@dataclass
class AltitudeStats:
    """Summary of an altitude time series (all metres)."""
    samples: int
    takeoff_m: float
    landing_m: float
    min_m: float
    max_m: float


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _altitude_stats(series: list[tuple[float, float]]) -> AltitudeStats | None:
    """Reduce an ``[(t, z), ...]`` series to start/end/min/max. None if empty."""
    if not series:
        return None
    zs = [z for _, z in series]
    return AltitudeStats(
        samples=len(zs),
        takeoff_m=series[0][1],
        landing_m=series[-1][1],
        min_m=min(zs),
        max_m=max(zs),
    )


def severity(drop_m: float, rate_mps: float) -> str:
    """Grade an altitude drop HIGH / MODERATE / LOW (ASSUMPTION, see docstring)."""
    if drop_m >= SEV_HIGH_DROP_M or rate_mps >= SEV_HIGH_RATE_MPS:
        return "HIGH"
    if drop_m >= SEV_MODERATE_DROP_M or rate_mps >= SEV_MODERATE_RATE_MPS:
        return "MODERATE"
    return "LOW"


def imu_severity(deviation_mps2: float) -> str:
    """Grade an IMU spike HIGH / MODERATE / LOW (ASSUMPTION, see docstring)."""
    if deviation_mps2 >= SEV_HIGH_IMU_DEV_MPS2:
        return "HIGH"
    if deviation_mps2 >= SEV_MODERATE_IMU_DEV_MPS2:
        return "MODERATE"
    return "LOW"


def build_report(structure, drop_events, imu_events=None) -> str:
    """Render the full plain-language incident report as a string.

    ``structure`` is an M1 ``BagStructure``; ``drop_events`` is the list of M2
    ``AltitudeDropEvent`` and ``imu_events`` the list of M4 ``ImuSpikeEvent``
    (either may be empty/None). Imported lazily by callers so this module has no
    hard dependency on the parser/detector packages.
    """
    imu_events = imu_events or []
    rule = "=" * 64
    sub = "-" * 64
    lines: list[str] = [rule, " FLIGHT INCIDENT REPORT", rule, ""]

    # --- 1. OVERVIEW -------------------------------------------------------
    lines.append(f"Source bag : {structure.path}")
    lines.append(f"Flight time: {structure.duration_s:.1f} s")
    lines.append(
        f"Data       : {structure.message_count} messages across "
        f"{len(structure.topics)} topic(s)"
    )
    for t in structure.topics:
        rate = t.msgcount / structure.duration_s if structure.duration_s > 0 else 0.0
        lines.append(
            f"             {t.topic:<14} {t.msgcount:>6} msgs "
            f"(~{rate:.0f} Hz)  {t.msgtype}"
        )
    lines.append("")

    # --- 2. FLIGHT SUMMARY -------------------------------------------------
    lines.append("FLIGHT SUMMARY")
    lines.append(sub)
    stats = _altitude_stats(structure.altitude_series)
    if stats is None:
        lines.append(
            "No altitude (PoseStamped) data was present, so no altitude "
            "profile could be reconstructed."
        )
    else:
        lines.append(
            f"The log covers {structure.duration_s:.1f} s of flight with "
            f"{stats.samples} position samples."
        )
        lines.append(
            f"Altitude began near {stats.takeoff_m:.1f} m and ended near "
            f"{stats.landing_m:.1f} m, ranging from a low of {stats.min_m:.1f} m "
            f"to a high of {stats.max_m:.1f} m."
        )
    if structure.imu_accel_series:
        accs = [a for _, a in structure.imu_accel_series]
        lines.append(
            f"IMU acceleration held near {_median(accs):.1f} m/s^2 baseline "
            f"(peak {max(accs):.1f} m/s^2) across {len(accs)} samples."
        )
    lines.append("")

    # --- 3. FINDINGS -------------------------------------------------------
    # Each finding is (severity, [text lines]); collected so the assessment can
    # count them and report the worst, and the section renders uniformly.
    findings: list[tuple[str, list[str]]] = []
    for e in drop_events:
        sev = severity(e.drop_m, e.rate_mps)
        findings.append((sev, [
            f"SEVERITY {sev} -- rapid altitude loss",
            f"    At t={e.start_time_s:.1f} s the aircraft lost "
            f"{e.drop_m:.1f} m in {e.duration_s:.1f} s ({e.rate_mps:.1f} m/s),",
            f"    descending from {e.peak_altitude_m:.1f} m to "
            f"{e.trough_altitude_m:.1f} m (bottomed out at t={e.end_time_s:.1f} s).",
        ]))
    for e in imu_events:
        sev = imu_severity(e.deviation_mps2)
        findings.append((sev, [
            f"SEVERITY {sev} -- IMU acceleration spike",
            f"    At t={e.peak_time_s:.1f} s acceleration spiked to "
            f"{e.peak_accel_mps2:.1f} m/s^2,",
            f"    +{e.deviation_mps2:.1f} m/s^2 above the "
            f"{e.baseline_mps2:.1f} m/s^2 baseline (held {e.duration_s:.2f} s).",
        ]))

    lines.append("FINDINGS")
    lines.append(sub)
    if not findings:
        lines.append(
            "No altitude drops or IMU spikes were detected. Flight looks nominal "
            "with respect to both checks."
        )
    else:
        n = len(findings)
        lines.append(f"{n} anomal{'ies' if n != 1 else 'y'} flagged:")
        lines.append("")
        for i, (_, block) in enumerate(findings, 1):
            lines.append(f"[{i}] {block[0]}")
            lines.extend(block[1:])
            lines.append("")
        lines.pop()  # drop trailing blank line from the loop
    lines.append("")

    # --- 4. ASSESSMENT -----------------------------------------------------
    lines.append("ASSESSMENT")
    lines.append(sub)
    if not findings:
        lines.append("Nominal -- no anomalies flagged for review.")
    else:
        n = len(findings)
        worst = max((sev for sev, _ in findings), key=lambda s: _SEV_ORDER[s])
        lines.append(
            f"{n} anomal{'ies' if n != 1 else 'y'} flagged for review; "
            f"highest severity: {worst}."
        )
    lines.append(rule)
    return "\n".join(lines)


def main() -> None:
    import argparse
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from detector import detect_altitude_drops  # noqa: E402
    from imu_detector import detect_imu_spikes  # noqa: E402
    from parser import parse_bag  # noqa: E402

    ap = argparse.ArgumentParser(
        description="Generate a plain-language incident report for a rosbag2 bag."
    )
    ap.add_argument("path", help="path to a rosbag2 bag directory")
    args = ap.parse_args()

    structure = parse_bag(args.path)
    drops = detect_altitude_drops(structure.altitude_series)
    spikes = detect_imu_spikes(structure.imu_accel_series)
    print(build_report(structure, drops, spikes))


if __name__ == "__main__":
    main()
