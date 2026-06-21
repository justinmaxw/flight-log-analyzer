"""M2 tests: the altitude-drop detector finds the injected anomaly and
rejects benign profiles (climbs, flat cruise, gentle descents)."""
from detector import detect_altitude_drops, format_drops
from generate_bag import generate_bag
from parser import parse_bag


def test_detects_injected_drop_on_synthetic_bag(tmp_path):
    """Ground truth: ~15 m loss over ~2 s at t=30->32 (cruise ~50 -> trough ~35)."""
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)

    events = detect_altitude_drops(s.altitude_series)

    assert len(events) == 1
    e = events[0]
    assert 12.0 < e.drop_m < 18.0            # ~15 m
    assert e.rate_mps > 4.0                   # rapid (~7.5 m/s)
    assert 29.0 < e.start_time_s < 31.0       # began at cruise peak ~t=30
    assert 31.0 < e.end_time_s < 33.0         # bottomed out ~t=32
    assert e.peak_altitude_m > 48.0
    assert e.trough_altitude_m < 38.0


def test_no_false_positive_on_pure_climb():
    series = [(t, 5.0 * t) for t in range(0, 11)]  # steady 5 m/s climb, no drop
    assert detect_altitude_drops(series) == []


def test_no_false_positive_on_flat_cruise():
    series = [(float(t), 50.0) for t in range(0, 20)]
    assert detect_altitude_drops(series) == []


def test_gentle_descent_below_rate_threshold_not_flagged():
    # Loses 10 m but over 20 s = 0.5 m/s, under the 2 m/s rate threshold.
    series = [(float(t), 50.0 - 0.5 * t) for t in range(0, 21)]
    assert detect_altitude_drops(series) == []


def test_small_dip_below_magnitude_threshold_not_flagged():
    # Sharp but tiny: 3 m drop in 1 s (6 m/s) -- fast enough but < 5 m magnitude.
    series = [(0.0, 50.0), (1.0, 47.0), (2.0, 50.0)]
    assert detect_altitude_drops(series) == []


def test_qualifying_drop_is_detected():
    series = [(0.0, 50.0), (1.0, 42.0), (2.0, 42.0)]  # 8 m in 1 s = 8 m/s
    events = detect_altitude_drops(series)
    assert len(events) == 1
    assert events[0].drop_m == 8.0
    assert events[0].rate_mps == 8.0


def test_threshold_overrides_let_smaller_drops_through():
    series = [(0.0, 50.0), (1.0, 47.0), (2.0, 50.0)]  # 3 m in 1 s = 3 m/s
    assert detect_altitude_drops(series, min_drop_m=2.0, min_rate_mps=1.0)


def test_empty_and_single_sample_series_are_safe():
    assert detect_altitude_drops([]) == []
    assert detect_altitude_drops([(0.0, 10.0)]) == []


def test_format_drops_readable_output():
    assert "No rapid altitude drops" in format_drops([])
    series = [(0.0, 50.0), (2.0, 35.0), (3.0, 35.0)]
    out = format_drops(detect_altitude_drops(series))
    assert "-15.0 m drop" in out
    assert "7.5 m/s" in out
