"""Flight-timeline visualization (Milestone 5, stretch).

Renders the parsed signals and detected anomalies as a single PNG with two
time-aligned panels:
  - Altitude (m) vs time, with each altitude-drop event shaded peak->trough.
  - IMU |acceleration| (m/s^2) vs time, with the median baseline drawn and each
    spike peak marked.
Anomaly markers are coloured by the same severity grade used in the text report
(HIGH red / MODERATE orange / LOW gold), so the picture and the report agree.

Uses matplotlib's non-interactive ``Agg`` backend, so it renders headless (no
display / no GUI event loop) -- safe to call from a CLI or CI.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: set before importing pyplot
import matplotlib.pyplot as plt  # noqa: E402

from report import imu_severity, severity  # noqa: E402

_SEV_COLOR = {"HIGH": "#d62728", "MODERATE": "#ff7f0e", "LOW": "#e6b800"}


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def plot_flight(structure, drop_events, imu_events, out_path) -> Path:
    """Render the flight timeline to ``out_path`` (PNG) and return its Path.

    ``structure`` is an M1 ``BagStructure``; ``drop_events`` / ``imu_events`` are
    the M2 / M4 event lists (either may be empty).
    """
    out = Path(out_path)
    fig, (ax_alt, ax_imu) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True, constrained_layout=True
    )
    fig.suptitle(f"Flight timeline — {Path(structure.path).name}", fontsize=13)

    # --- Altitude panel ---------------------------------------------------
    if structure.altitude_series:
        at = [t for t, _ in structure.altitude_series]
        az = [z for _, z in structure.altitude_series]
        ax_alt.plot(at, az, color="#1f77b4", lw=1.2, label="altitude")
        ax_alt.legend(loc="upper right", fontsize=8)
    for e in drop_events:
        color = _SEV_COLOR[severity(e.drop_m, e.rate_mps)]
        ax_alt.axvspan(e.start_time_s, e.end_time_s, color=color, alpha=0.25)
        ax_alt.annotate(
            f"-{e.drop_m:.0f} m\n{e.rate_mps:.1f} m/s",
            xy=(e.end_time_s, e.trough_altitude_m),
            xytext=(0, -28), textcoords="offset points",
            ha="center", va="top", fontsize=8, color=color,
            arrowprops=dict(arrowstyle="->", color=color, lw=1),
        )
    ax_alt.set_ylabel("Altitude (m)")
    ax_alt.grid(True, alpha=0.3)

    # --- IMU panel --------------------------------------------------------
    if structure.imu_accel_series:
        it = [t for t, _ in structure.imu_accel_series]
        ia = [a for _, a in structure.imu_accel_series]
        ax_imu.plot(it, ia, color="#2ca02c", lw=0.8, label="|accel|")
        baseline = _median(ia)
        ax_imu.axhline(
            baseline, color="gray", ls="--", lw=1,
            label=f"baseline {baseline:.1f}",
        )
        ax_imu.legend(loc="upper right", fontsize=8)
    for e in imu_events:
        color = _SEV_COLOR[imu_severity(e.deviation_mps2)]
        ax_imu.plot(e.peak_time_s, e.peak_accel_mps2, "v", color=color, ms=9)
        ax_imu.annotate(
            f"+{e.deviation_mps2:.0f} m/s²",
            xy=(e.peak_time_s, e.peak_accel_mps2),
            xytext=(0, 10), textcoords="offset points",
            ha="center", va="bottom", fontsize=8, color=color,
        )
    ax_imu.set_ylabel("IMU |accel| (m/s²)")
    ax_imu.set_xlabel("Time since start (s)")
    ax_imu.grid(True, alpha=0.3)

    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def main() -> None:
    import argparse
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from detector import detect_altitude_drops  # noqa: E402
    from imu_detector import detect_imu_spikes  # noqa: E402
    from parser import parse_bag  # noqa: E402

    ap = argparse.ArgumentParser(description="Plot a flight timeline from a rosbag2 bag.")
    ap.add_argument("path", help="path to a rosbag2 bag directory")
    ap.add_argument("-o", "--out", default="flight_timeline.png", help="output PNG path")
    args = ap.parse_args()

    structure = parse_bag(args.path)
    drops = detect_altitude_drops(structure.altitude_series)
    spikes = detect_imu_spikes(structure.imu_accel_series)
    out = plot_flight(structure, drops, spikes, args.out)
    print(f"Wrote plot -> {out}")


if __name__ == "__main__":
    main()
