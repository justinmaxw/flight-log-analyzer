"""M4 test: the one-command pipeline analyzes an arbitrary bag path end-to-end
and surfaces both injected anomalies in the report."""
from generate_bag import generate_bag
from main import analyze_bag


def test_analyze_bag_on_arbitrary_path(tmp_path):
    bag = generate_bag(tmp_path / "some_flight", duration_s=60.0)

    report = analyze_bag(bag)

    assert "FLIGHT INCIDENT REPORT" in report
    assert "2 anomalies flagged" in report
    assert "rapid altitude loss" in report
    assert "IMU acceleration spike" in report
