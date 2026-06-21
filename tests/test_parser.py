"""M1 tests: the parser returns correct structure and finds the injected anomaly."""
from generate_bag import IMU_TOPIC, POSE_TOPIC, generate_bag
from parser import parse_bag


def test_structure_fields(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)

    assert s.message_count == 3600
    assert {t.topic for t in s.topics} == {POSE_TOPIC, IMU_TOPIC}
    # rosbag2 duration = (last - first timestamp) + 1 ns; ~59.98 s for this profile.
    assert 59.0 < s.duration_s < 61.0
    assert s.start_time_ns <= s.end_time_ns


def test_altitude_series_extracted_and_sorted(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0, pose_hz=10.0)
    s = parse_bag(bag)

    assert len(s.altitude_series) == 600
    times = [t for t, _ in s.altitude_series]
    assert times == sorted(times)


def test_injected_altitude_drop_present(tmp_path):
    """Ground-truth check: a ~15 m drop exists near t=30-32 s (cruise ~50 -> ~35)."""
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)

    cruise = [z for t, z in s.altitude_series if 15.0 <= t <= 29.0]
    trough = [z for t, z in s.altitude_series if 31.5 <= t <= 33.0]
    assert cruise and trough
    cruise_alt = sum(cruise) / len(cruise)
    min_trough = min(trough)
    assert cruise_alt > 48.0          # cruising near 50 m
    assert min_trough < 38.0          # dropped toward 35 m
    assert cruise_alt - min_trough > 10.0   # drop magnitude is real (~15 m)
