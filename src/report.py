"""Plain-language incident report generator (Milestone 3).

Turns the machine-readable outputs of the earlier milestones --
``BagStructure`` (M1 parser) and a list of ``AltitudeDropEvent`` (M2 detector)
-- into a single human-readable incident report a non-engineer can skim:

  1. OVERVIEW    -- what the log is (source, flight time, data channels).
  2. FLIGHT      -- what happened (altitude profile, data rates).
  3. FINDINGS    -- what looked anomalous, in plain English, with severity.
  4. ASSESSMENT  -- one-line verdict (nominal vs. N items flagged for review).

This module is pure formatting: it computes nothing about the flight that the
parser/detector did not already establish, so it stays honest and testable.
Stdlib only -- no new dependencies.

Severity heuristic (ASSUMPTION -- flagged for sanity-check, not a standard):
  We grade each altitude drop from its magnitude and rate, whichever is worse:
    HIGH      drop >= 10 m  OR  rate >= 5.0 m/s
    MODERATE  drop >=  5 m  OR  rate >= 2.0 m/s   (i.e. cleared the detector)
    LOW       anything else that was still flagged
  These bands are first-pass engineering guesses for a small UAV, chosen so the
  synthetic anomaly (~15 m at ~7.5 m/s) reads as HIGH. Revisit against real logs.
"""
from __future__ import annotations

from dataclasses import dataclass

# Severity band thresholds (ASSUMPTION -- see module docstring).
SEV_HIGH_DROP_M = 10.0
SEV_HIGH_RATE_MPS = 5.0
SEV_MODERATE_DROP_M = 5.0
SEV_MODERATE_RATE_MPS = 2.0


@dataclass
class AltitudeStats:
    """Summary of an altitude time series (all metres)."""
    samples: int
    takeoff_m: float
    landing_m: float
    min_m: float
    max_m: float


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


def build_report(structure, events) -> str:
    """Render the full plain-language incident report as a string.

    ``structure`` is an M1 ``BagStructure``; ``events`` is the list of M2
    ``AltitudeDropEvent`` (may be empty). Imported lazily by callers so this
    module has no hard dependency on the parser/detector packages.
    """
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
    lines.append("")

    # --- 3. FINDINGS -------------------------------------------------------
    lines.append("FINDINGS")
    lines.append(sub)
    if not events:
        lines.append(
            "No rapid altitude drops were detected. Flight looks nominal with "
            "respect to the altitude-drop check."
        )
    else:
        n = len(events)
        lines.append(
            f"{n} rapid altitude drop{'s' if n != 1 else ''} flagged:"
        )
        lines.append("")
        for i, e in enumerate(events, 1):
            sev = severity(e.drop_m, e.rate_mps)
            lines.append(f"[{i}] SEVERITY {sev} -- rapid altitude loss")
            lines.append(
                f"    At t={e.start_time_s:.1f} s the aircraft lost "
                f"{e.drop_m:.1f} m in {e.duration_s:.1f} s "
                f"({e.rate_mps:.1f} m/s),"
            )
            lines.append(
                f"    descending from {e.peak_altitude_m:.1f} m to "
                f"{e.trough_altitude_m:.1f} m (bottomed out at "
                f"t={e.end_time_s:.1f} s)."
            )
            lines.append("")
        lines.pop()  # drop trailing blank line from the loop
    lines.append("")

    # --- 4. ASSESSMENT -----------------------------------------------------
    lines.append("ASSESSMENT")
    lines.append(sub)
    if not events:
        lines.append("Nominal -- no anomalies flagged for review.")
    else:
        worst = _worst_severity(events)
        n = len(events)
        lines.append(
            f"{n} altitude anomal{'ies' if n != 1 else 'y'} flagged for review; "
            f"highest severity: {worst}."
        )
    lines.append(rule)
    return "\n".join(lines)


def _worst_severity(events) -> str:
    """Highest severity across events, by HIGH > MODERATE > LOW ordering."""
    order = {"HIGH": 3, "MODERATE": 2, "LOW": 1}
    return max(
        (severity(e.drop_m, e.rate_mps) for e in events),
        key=lambda s: order[s],
    )


def main() -> None:
    import argparse
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from detector import detect_altitude_drops  # noqa: E402
    from parser import parse_bag  # noqa: E402

    ap = argparse.ArgumentParser(
        description="Generate a plain-language incident report for a rosbag2 bag."
    )
    ap.add_argument("path", help="path to a rosbag2 bag directory")
    args = ap.parse_args()

    structure = parse_bag(args.path)
    events = detect_altitude_drops(structure.altitude_series)
    print(build_report(structure, events))


if __name__ == "__main__":
    main()
