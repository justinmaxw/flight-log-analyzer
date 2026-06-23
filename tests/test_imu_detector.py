"""M4 tests: the IMU-spike detector finds the injected acceleration jolt and
rejects steady IMU data (no spike)."""
from generate_bag import generate_bag
from imu_detector import detect_imu_spikes, format_spikes
from parser import parse_bag


def test_detects_injected_spike_on_synthetic_bag(tmp_path):
    """Ground truth: ~31 m/s^2 jolt above ~9.81 baseline near t=45 s."""
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)

    events = detect_imu_spikes(s.imu_accel_series)

    assert len(events) == 1
    e = events[0]
    assert e.deviation_mps2 > 20.0            # ~31 m/s^2 over baseline
    assert 9.0 < e.baseline_mps2 < 10.6       # ~gravity, not dragged up by the spike
    assert 44.0 < e.peak_time_s < 46.0        # injected at t=45
    assert e.peak_accel_mps2 > 35.0


def test_no_false_positive_on_steady_gravity():
    series = [(t * 0.02, 9.81) for t in range(200)]  # perfectly steady baseline
    assert detect_imu_spikes(series) == []


def test_no_false_positive_on_small_noise():
    # Deterministic tiny ripple around gravity, all < 5 m/s^2 deviation.
    series = [(t * 0.02, 9.81 + (0.05 if t % 2 else -0.05)) for t in range(200)]
    assert detect_imu_spikes(series) == []


def test_single_qualifying_spike_detected():
    series = [(float(t), 9.8) for t in range(20)]
    series[10] = (10.0, 30.0)  # one big sample
    events = detect_imu_spikes(series)
    assert len(events) == 1
    assert events[0].peak_time_s == 10.0
    assert abs(events[0].peak_accel_mps2 - 30.0) < 1e-9


def test_consecutive_spike_samples_group_into_one_event():
    series = [(float(t), 9.8) for t in range(20)]
    series[10] = (10.0, 40.0)
    series[11] = (11.0, 45.0)   # higher -> should be the reported peak
    series[12] = (12.0, 38.0)
    events = detect_imu_spikes(series)
    assert len(events) == 1
    e = events[0]
    assert e.start_time_s == 10.0
    assert e.end_time_s == 12.0
    assert e.peak_time_s == 11.0
    assert e.duration_s == 2.0


def test_dev_threshold_override_lets_smaller_spike_through():
    series = [(float(t), 9.8) for t in range(20)]
    series[5] = (5.0, 13.0)  # +3.2 m/s^2: under default floor, over a 2.0 override
    assert detect_imu_spikes(series) == []
    assert detect_imu_spikes(series, min_dev_mps2=2.0)


def test_empty_and_single_sample_series_are_safe():
    assert detect_imu_spikes([]) == []
    assert detect_imu_spikes([(0.0, 9.81)]) == []


def test_format_spikes_readable_output():
    assert "No acceleration spikes" in format_spikes([])
    series = [(float(t), 9.8) for t in range(20)]
    series[10] = (10.0, 40.0)
    out = format_spikes(detect_imu_spikes(series))
    assert "spike" in out
    assert "t=10.0 s" in out
