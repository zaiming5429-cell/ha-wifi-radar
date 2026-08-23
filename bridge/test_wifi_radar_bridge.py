import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wifi_radar_bridge import RadarState


def sample(timestamp: str, score: float, rssi: float = -58.0) -> dict:
    return {"timestamp": timestamp, "vibration_score": score, "rssi_dbm": rssi}


class RadarStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "radar.json"
        self.state = RadarState(self.path, stale_seconds=10)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, samples: list[dict], updated_at: str = "2026-08-23T12:00:00+00:00") -> None:
        self.path.write_text(json.dumps({
            "status": "online", "updated_at": updated_at,
            "baseline": {"mean_dbm": -58.0, "stddev_db": 0.5, "sample_count": 30},
            "current": samples[-1] if samples else {}, "samples": samples,
        }), encoding="utf-8")

    @patch("wifi_radar_bridge.time.time", return_value=1787486401.0)
    def test_passage_merges_and_ends(self, _time: object) -> None:
        rows = [
            sample("2026-08-23T12:00:00+00:00", 50, -60),
            sample("2026-08-23T12:00:01+00:00", 80, -64),
            sample("2026-08-23T12:00:02+00:00", 100, -67),
            sample("2026-08-23T12:00:03+00:00", 30),
            sample("2026-08-23T12:00:04+00:00", 20),
            sample("2026-08-23T12:00:05+00:00", 10),
        ]
        self.write(rows)
        self.state.update()
        result = self.state.snapshot()
        self.assertFalse(result["passage"]["active"])
        self.assertEqual(result["passage"]["count_since_start"], 1)
        self.assertEqual(result["passage"]["last"]["peak_score"], 100)
        self.assertEqual(result["passage"]["last"]["max_delta_db"], 9)
        self.assertEqual(result["passage"]["last"]["duration_seconds"], 4)

    @patch("wifi_radar_bridge.time.time", return_value=1787486500.0)
    def test_stale_source_is_unavailable(self, _time: object) -> None:
        self.write([sample("2026-08-23T12:00:00+00:00", 1)])
        self.state.update()
        result = self.state.snapshot()
        self.assertTrue(result["stale"])
        self.assertFalse(result["available"])

    def test_reprocessing_same_samples_is_bounded(self) -> None:
        rows = [sample("2026-08-23T12:00:00+00:00", 50), sample("2026-08-23T12:00:01+00:00", 60)]
        self.write(rows)
        self.state.update()
        self.state.update()
        self.assertEqual(self.state.snapshot()["passage"]["count_since_start"], 1)


if __name__ == "__main__":
    unittest.main()
