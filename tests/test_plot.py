"""M5 tests: the flight-timeline plot renders a valid PNG headless (Agg backend),
for both the anomalous synthetic bag and an empty-signal edge case."""
from detector import detect_altitude_drops
from generate_bag import generate_bag
from imu_detector import detect_imu_spikes
from parser import parse_bag
from plot import plot_flight

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_plot_writes_valid_png(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0)
    s = parse_bag(bag)
    drops = detect_altitude_drops(s.altitude_series)
    spikes = detect_imu_spikes(s.imu_accel_series)

    out = plot_flight(s, drops, spikes, tmp_path / "timeline.png")

    assert out.exists()
    data = out.read_bytes()
    assert data[:8] == _PNG_MAGIC      # real PNG
    assert len(data) > 5000            # non-trivial image, not a blank stub


def test_plot_handles_empty_signals(tmp_path):
    class _Stub:
        path = "fake/bag"
        duration_s = 10.0
        message_count = 0
        topics = []
        altitude_series = []
        imu_accel_series = []

    out = plot_flight(_Stub(), [], [], tmp_path / "empty.png")
    assert out.exists()
    assert out.read_bytes()[:8] == _PNG_MAGIC
