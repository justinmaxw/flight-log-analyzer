"""IMU-spike detector (Milestone 4).

Consumes the time-sorted ``imu_accel_series`` produced by the structural parser
(``list[(time_s, accel_magnitude_m_s2)]`` -- the magnitude of the IMU's linear
acceleration vector) and flags brief *spikes*: samples whose acceleration jumps
far above the steady baseline (a sudden jolt, impact, or saturation).

Algorithm -- robust-baseline deviation scan:
  The baseline is the **median** of the whole series, and the spread is the
  **median absolute deviation (MAD)**. Both are robust: a short, large spike
  barely moves them, so the baseline stays near the true resting value (~9.81
  m/s^2, gravity, for a level airframe) instead of being dragged up by the very
  event we want to find -- the classic failure of a mean/standard-deviation
  threshold. A sample is flagged when its deviation from the baseline exceeds
  BOTH an absolute floor (``min_dev_mps2``) and a robust multiple of the spread
  (``k_mad`` * 1.4826 * MAD). Consecutive flagged samples form one event,
  reported at its peak.

Thresholds are conservative defaults, flagged for sanity-check (all assumptions):
  min_dev_mps2 = 5.0 m/s^2 -- ignore wobble smaller than this above baseline
  k_mad        = 6.0       -- and require 6 robust-sigma, so quiet logs don't
                              false-positive when MAD (hence the sigma) is tiny
The 1.4826 factor scales MAD to a standard-deviation-equivalent for ~Gaussian
noise. The synthetic bag's injected jolt is ~31 m/s^2 above baseline, far clear
of the floor. Real thresholds depend on the airframe and IMU placement.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

DEFAULT_MIN_DEV_MPS2 = 5.0
DEFAULT_K_MAD = 6.0
_MAD_TO_SIGMA = 1.4826  # MAD -> std-dev equivalent for Gaussian noise


@dataclass
class ImuSpikeEvent:
    """A single detected acceleration spike (run of flagged samples)."""
    start_time_s: float    # first flagged sample in the run
    end_time_s: float      # last flagged sample in the run
    peak_time_s: float     # time of the largest deviation
    peak_accel_mps2: float
    baseline_mps2: float

    @property
    def deviation_mps2(self) -> float:
        return self.peak_accel_mps2 - self.baseline_mps2

    @property
    def duration_s(self) -> float:
        return self.end_time_s - self.start_time_s


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def detect_imu_spikes(
    series: list[tuple[float, float]],
    min_dev_mps2: float = DEFAULT_MIN_DEV_MPS2,
    k_mad: float = DEFAULT_K_MAD,
) -> list[ImuSpikeEvent]:
    """Return acceleration-spike events in a time-sorted IMU magnitude series.

    ``series`` is ``[(time_s, accel_magnitude), ...]`` sorted by time. A sample
    is flagged when its acceleration exceeds the median baseline by at least
    ``min_dev_mps2`` AND by at least ``k_mad`` robust sigma. Consecutive flagged
    samples form one event, reported at its peak.
    """
    n = len(series)
    if n < 2:
        return []
    accs = [a for _, a in series]
    baseline = _median(accs)
    mad = _median([abs(a - baseline) for a in accs])
    robust_gate = k_mad * _MAD_TO_SIGMA * mad
    # Effective gate: must clear both the absolute floor and the robust multiple.
    gate = max(min_dev_mps2, robust_gate)

    flagged = [i for i, a in enumerate(accs) if a - baseline >= gate]
    if not flagged:
        return []

    # Group consecutive indices into runs; emit each run's peak.
    events: list[ImuSpikeEvent] = []
    run: list[int] = [flagged[0]]

    def emit(idxs: list[int]) -> None:
        peak_i = max(idxs, key=lambda i: accs[i])
        events.append(
            ImuSpikeEvent(
                start_time_s=series[idxs[0]][0],
                end_time_s=series[idxs[-1]][0],
                peak_time_s=series[peak_i][0],
                peak_accel_mps2=accs[peak_i],
                baseline_mps2=baseline,
            )
        )

    for i in flagged[1:]:
        if i == run[-1] + 1:
            run.append(i)
        else:
            emit(run)
            run = [i]
    emit(run)
    return events


def format_spikes(
    events: list[ImuSpikeEvent],
    min_dev_mps2: float = DEFAULT_MIN_DEV_MPS2,
) -> str:
    """Plain-language summary of detected IMU spikes."""
    header = f"IMU-spike detector (>= {min_dev_mps2:.0f} m/s^2 above baseline):"
    if not events:
        return header + "\n  No acceleration spikes detected."
    lines = [header]
    for i, e in enumerate(events, 1):
        lines.append(
            f"  [{i}] +{e.deviation_mps2:.1f} m/s^2 spike: peak "
            f"{e.peak_accel_mps2:.1f} m/s^2 vs baseline {e.baseline_mps2:.1f}, "
            f"t={e.peak_time_s:.1f} s (held {e.duration_s:.2f} s)"
        )
    return "\n".join(lines)


def main() -> None:
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from parser import parse_bag  # noqa: E402

    ap = argparse.ArgumentParser(description="Detect IMU acceleration spikes in a rosbag2 bag.")
    ap.add_argument("path", help="path to a rosbag2 bag directory")
    ap.add_argument("--min-dev", type=float, default=DEFAULT_MIN_DEV_MPS2)
    args = ap.parse_args()

    structure = parse_bag(args.path)
    events = detect_imu_spikes(structure.imu_accel_series, args.min_dev)
    print(format_spikes(events, args.min_dev))


if __name__ == "__main__":
    main()
