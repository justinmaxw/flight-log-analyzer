"""Altitude-drop detector (Milestone 2).

Consumes the time-sorted ``altitude_series`` produced by the structural parser
(``list[(time_s, altitude_m)]``) and flags *rapid* altitude losses.

Algorithm — bounded-lookback descent scan:
  For each sample we look back over a short ``window_s`` window and find the
  recent high altitude. The "drop" at that sample is recent-high minus current
  altitude; the rate is that drop over the elapsed time from the high. Samples
  whose drop and rate both clear the thresholds are grouped (consecutive samples
  = one event), and each event is summarized by its deepest point.

  Two design choices keep the reported numbers honest and noise-robust:
   - The lookback is *bounded* to ``window_s`` so a much earlier, unrelated high
     can't be charged against a later drop (keeps drops local to their phase).
   - The "recent high" is pinned to the *latest* sample within ``peak_tol_m`` of
     the window max -- i.e. the last moment we were at altitude *before* the
     descent -- so a noisy plateau doesn't inflate the measured duration. This
     was the bug in a naive peak-to-trough scan: a noise spike early in a long
     cruise stretched the duration and hid a real rapid drop.

Thresholds are conservative defaults, flagged for sanity-check (all assumptions):
  min_drop_m   = 5.0 m   -- ignore dips smaller than this (noise / minor maneuver)
  min_rate_mps = 2.0 m/s -- only flag *rapid* loss; gentle descents don't count
  window_s     = 3.0 s   -- lookback horizon; must exceed expected drop duration
  peak_tol_m   = 0.5 m   -- "at altitude" band; comfortably above ~0.05 m sensor noise
The synthetic bag's injected anomaly is ~15 m over ~2 s (~7.5 m/s), well clear
of the drop/rate thresholds and shorter than the lookback window.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

DEFAULT_MIN_DROP_M = 5.0
DEFAULT_MIN_RATE_MPS = 2.0
DEFAULT_WINDOW_S = 3.0
DEFAULT_PEAK_TOL_M = 0.5


@dataclass
class AltitudeDropEvent:
    """A single detected rapid altitude loss (recent high -> trough)."""
    start_time_s: float   # time of the recent high the drop fell from
    end_time_s: float     # time of the trough (lowest point of the drop)
    peak_altitude_m: float
    trough_altitude_m: float

    @property
    def drop_m(self) -> float:
        return self.peak_altitude_m - self.trough_altitude_m

    @property
    def duration_s(self) -> float:
        return self.end_time_s - self.start_time_s

    @property
    def rate_mps(self) -> float:
        """Average descent rate over the drop (m/s). 0 if duration is ~0."""
        return self.drop_m / self.duration_s if self.duration_s > 0 else 0.0


def detect_altitude_drops(
    series: list[tuple[float, float]],
    min_drop_m: float = DEFAULT_MIN_DROP_M,
    min_rate_mps: float = DEFAULT_MIN_RATE_MPS,
    window_s: float = DEFAULT_WINDOW_S,
    peak_tol_m: float = DEFAULT_PEAK_TOL_M,
) -> list[AltitudeDropEvent]:
    """Return rapid altitude-loss events in a time-sorted altitude series.

    ``series`` is ``[(time_s, altitude_m), ...]`` sorted by time (the parser
    guarantees this). A sample is flagged when, relative to the recent high
    within the preceding ``window_s`` seconds, it has lost >= ``min_drop_m``
    metres at an average rate >= ``min_rate_mps``. Consecutive flagged samples
    form one event, reported at its deepest (largest-drop) point.
    """
    n = len(series)
    if n < 2:
        return []
    times = [t for t, _ in series]
    alts = [z for _, z in series]

    # Per-flagged-sample records: (index, peak_t, peak_z, trough_t, trough_z, drop).
    flagged: list[tuple[int, float, float, float, float, float]] = []
    left = 0
    for i in range(n):
        t_i, z_i = times[i], alts[i]
        while times[left] < t_i - window_s:
            left += 1
        win_max = max(alts[left : i + 1])
        # "Recent high" = latest sample still within peak_tol_m of the window max,
        # i.e. the last moment at altitude before the descent (ignores noise).
        peak_idx = max(k for k in range(left, i + 1) if alts[k] >= win_max - peak_tol_m)
        peak_t, peak_z = times[peak_idx], alts[peak_idx]
        drop = peak_z - z_i
        dt = t_i - peak_t
        if dt > 0 and drop >= min_drop_m and drop / dt >= min_rate_mps:
            flagged.append((i, peak_t, peak_z, t_i, z_i, drop))

    # Group consecutive flagged samples; emit each group's deepest point.
    events: list[AltitudeDropEvent] = []
    group: list[tuple[int, float, float, float, float, float]] = []

    def emit(g: list[tuple[int, float, float, float, float, float]]) -> None:
        _, pt, pz, tt, tz, _ = max(g, key=lambda r: r[5])
        events.append(AltitudeDropEvent(pt, tt, pz, tz))

    for rec in flagged:
        if group and rec[0] != group[-1][0] + 1:
            emit(group)
            group = []
        group.append(rec)
    if group:
        emit(group)
    return events


def format_drops(
    events: list[AltitudeDropEvent],
    min_drop_m: float = DEFAULT_MIN_DROP_M,
    min_rate_mps: float = DEFAULT_MIN_RATE_MPS,
) -> str:
    """Plain-language summary of detected altitude drops."""
    header = (
        f"Altitude-drop detector (>= {min_drop_m:.0f} m loss at "
        f">= {min_rate_mps:.0f} m/s):"
    )
    if not events:
        return header + "\n  No rapid altitude drops detected."
    lines = [header]
    for i, e in enumerate(events, 1):
        lines.append(
            f"  [{i}] -{e.drop_m:.1f} m drop over {e.duration_s:.1f} s "
            f"({e.rate_mps:.1f} m/s): {e.peak_altitude_m:.1f} m -> "
            f"{e.trough_altitude_m:.1f} m, t={e.start_time_s:.1f}->{e.end_time_s:.1f} s"
        )
    return "\n".join(lines)


def main() -> None:
    from parser import parse_bag  # local import: avoids hard dep when used as a lib

    ap = argparse.ArgumentParser(description="Detect altitude drops in a rosbag2 bag.")
    ap.add_argument("path", help="path to a rosbag2 bag directory")
    ap.add_argument("--min-drop", type=float, default=DEFAULT_MIN_DROP_M)
    ap.add_argument("--min-rate", type=float, default=DEFAULT_MIN_RATE_MPS)
    args = ap.parse_args()

    structure = parse_bag(args.path)
    events = detect_altitude_drops(structure.altitude_series, args.min_drop, args.min_rate)
    print(format_drops(events, args.min_drop, args.min_rate))


if __name__ == "__main__":
    main()
