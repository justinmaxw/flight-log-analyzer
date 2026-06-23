"""M3 tests: the incident report reads correctly for a nominal flight and for
the synthetic bag's injected altitude drop, and severity grading is sane."""
from detector import detect_altitude_drops
from generate_bag import generate_bag
from parser import parse_bag
from report import build_report, severity


def test_report_has_all_four_sections(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    events = detect_altitude_drops(s.altitude_series)
    report = build_report(s, events)

    for section in ("FLIGHT INCIDENT REPORT", "FLIGHT SUMMARY", "FINDINGS", "ASSESSMENT"):
        assert section in report


def test_report_flags_injected_drop(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    events = detect_altitude_drops(s.altitude_series)
    report = build_report(s, events)

    assert len(events) == 1
    assert "1 rapid altitude drop flagged" in report
    assert "SEVERITY HIGH" in report           # ~15 m / ~7.5 m/s -> HIGH
    assert "flagged for review" in report
    assert "Nominal" not in report
    # Overview reflects real channels and flight time.
    assert "/flight/pose" in report
    assert "/flight/imu" in report
    assert "60.0 s" in report


def test_report_nominal_when_no_events(tmp_path):
    # Use a real bag structure but pass [] events to exercise the nominal
    # branch deterministically (independent of detector thresholds).
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    report = build_report(s, [])

    assert "No rapid altitude drops were detected" in report
    assert "Nominal -- no anomalies flagged" in report
    assert "SEVERITY" not in report


def test_report_handles_missing_altitude_series():
    class _Stub:
        path = "fake/bag"
        duration_s = 10.0
        message_count = 100
        topics = []
        altitude_series = []

    report = build_report(_Stub(), [])
    assert "no altitude profile could be reconstructed" in report.lower()


def test_severity_bands():
    assert severity(15.0, 7.5) == "HIGH"       # synthetic anomaly
    assert severity(10.0, 1.0) == "HIGH"       # magnitude alone
    assert severity(1.0, 5.0) == "HIGH"        # rate alone
    assert severity(6.0, 2.0) == "MODERATE"
    assert severity(5.0, 1.0) == "MODERATE"    # cleared min drop
    assert severity(3.0, 1.5) == "LOW"
