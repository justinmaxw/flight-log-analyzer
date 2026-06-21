"""M1 tests: the generated bag has the expected topics, types, and counts."""
from rosbags.rosbag2 import Reader

from generate_bag import (
    IMU_TOPIC,
    IMU_TYPE,
    POSE_TOPIC,
    POSE_TYPE,
    generate_bag,
)


def test_bag_files_written(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight")
    names = {p.name for p in bag.iterdir()}
    assert "metadata.yaml" in names
    assert any(n.endswith(".db3") for n in names)


def test_topics_types_and_counts(tmp_path):
    bag = generate_bag(tmp_path / "synthetic_flight", duration_s=60.0, pose_hz=10.0, imu_hz=50.0)
    reader = Reader(bag)
    reader.open()
    try:
        by_topic = {c.topic: c for c in reader.connections}
        assert set(by_topic) == {POSE_TOPIC, IMU_TOPIC}
        assert by_topic[POSE_TOPIC].msgtype == POSE_TYPE
        assert by_topic[IMU_TOPIC].msgtype == IMU_TYPE
        # 60 s @ 10 Hz and 50 Hz
        assert by_topic[POSE_TOPIC].msgcount == 600
        assert by_topic[IMU_TOPIC].msgcount == 3000
        assert reader.message_count == 3600
    finally:
        reader.close()


def test_deterministic(tmp_path):
    # Determinism means identical message *content* for a fixed seed. (Raw .db3
    # bytes differ because rosbag2 embeds the bag's directory name in the file.)
    from parser import parse_bag

    s1 = parse_bag(generate_bag(tmp_path / "a", duration_s=5.0))
    s2 = parse_bag(generate_bag(tmp_path / "b", duration_s=5.0))
    assert s1.message_count == s2.message_count
    assert s1.altitude_series == s2.altitude_series
