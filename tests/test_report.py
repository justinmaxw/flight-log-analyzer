"""M3/M4 tests: the incident report reads correctly for a nominal flight and for
the synthetic bag's injected anomalies (altitude drop + IMU spike), and severity
grading is sane."""
from detector import detect_altitude_drops
from generate_bag import generate_bag
from imu_detector import detect_imu_spikes
from parser import parse_bag
from report import build_report, imu_severity, severity


def test_report_has_all_four_sections(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    drops = detect_altitude_drops(s.altitude_series)
    spikes = detect_imu_spikes(s.imu_accel_series)
    report = build_report(s, drops, spikes)

    for section in ("FLIGHT INCIDENT REPORT", "FLIGHT SUMMARY", "FINDINGS", "ASSESSMENT"):
        assert section in report


def test_report_flags_both_injected_anomalies(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    drops = detect_altitude_drops(s.altitude_series)
    spikes = detect_imu_spikes(s.imu_accel_series)
    report = build_report(s, drops, spikes)

    assert len(drops) == 1 and len(spikes) == 1
    assert "2 anomalies flagged" in report
    assert "rapid altitude loss" in report
    assert "IMU acceleration spike" in report
    assert "highest severity: HIGH" in report      # both ~HIGH
    assert "Nominal" not in report
    # Overview reflects real channels and flight time.
    assert "/flight/pose" in report
    assert "/flight/imu" in report
    assert "60.0 s" in report


def test_report_single_anomaly_grammar(tmp_path):
    """With only the altitude drop, the report should say '1 anomaly' (singular)."""
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    drops = detect_altitude_drops(s.altitude_series)
    report = build_report(s, drops)  # imu_events defaults to none

    assert "1 anomaly flagged" in report
    assert "IMU acceleration spike" not in report


def test_report_nominal_when_no_events(tmp_path):
    # Use a real bag structure but pass empty event lists to exercise the nominal
    # branch deterministically (independent of detector thresholds).
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    report = build_report(s, [], [])

    assert "No altitude drops or IMU spikes were detected" in report
    assert "Nominal -- no anomalies flagged" in report
    assert "SEVERITY" not in report


def test_report_handles_missing_altitude_series():
    class _Stub:
        path = "fake/bag"
        duration_s = 10.0
        message_count = 100
        topics = []
        altitude_series = []
        imu_accel_series = []

    report = build_report(_Stub(), [])
    assert "no altitude profile could be reconstructed" in report.lower()


def test_severity_bands():
    assert severity(15.0, 7.5) == "HIGH"       # synthetic altitude anomaly
    assert severity(10.0, 1.0) == "HIGH"       # magnitude alone
    assert severity(1.0, 5.0) == "HIGH"        # rate alone
    assert severity(6.0, 2.0) == "MODERATE"
    assert severity(5.0, 1.0) == "MODERATE"    # cleared min drop
    assert severity(3.0, 1.5) == "LOW"


def test_imu_severity_bands():
    assert imu_severity(31.0) == "HIGH"        # synthetic jolt
    assert imu_severity(20.0) == "HIGH"
    assert imu_severity(8.0) == "MODERATE"
    assert imu_severity(5.0) == "MODERATE"     # cleared min dev
    assert imu_severity(3.0) == "LOW"
