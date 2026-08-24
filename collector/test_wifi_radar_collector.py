import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wifi_radar_collector import WifiReading, _score_reading, collect_once, parse_iw, parse_netsh


class CollectorParsingTest(unittest.TestCase):
    def test_windows_netsh_english(self) -> None:
        reading = parse_netsh("State : connected\nSignal : 78%\nChannel : 36\n")
        self.assertEqual(reading.rssi_dbm, -61.0)
        self.assertEqual(reading.signal_percent, 78)

    def test_windows_netsh_localized_percent_fallback(self) -> None:
        reading = parse_netsh("X : Y\nLocalized signal : 64%\n")
        self.assertEqual(reading.rssi_dbm, -68.0)

    def test_linux_iw(self) -> None:
        reading = parse_iw("Connected to hidden\n\tsignal: -57 dBm\n")
        self.assertEqual(reading.rssi_dbm, -57.0)

    def test_custom_scoring_requires_calibration(self) -> None:
        reading = WifiReading(-50.0, None, None, None, None, None)
        previous = [{"rssi_dbm": -60.0, "vibration_score": 80.0} for _ in range(19)]
        _baseline, _score, _level, candidate = _score_reading(reading, previous)
        self.assertFalse(candidate)

    def test_idle_step_change_is_rejected(self) -> None:
        values = [-64, -64, -66, -66, -66, -64, -64]
        previous = [{"rssi_dbm": value, "vibration_score": 80.0} for value in ([-64] * 20 + values)]
        _baseline, _score, _level, candidate = _score_reading(WifiReading(-63.0, None, None, None, None, None), previous)
        self.assertFalse(candidate)

    def test_real_passage_waveform_is_retained(self) -> None:
        values = [-57, -60, -60, -64, -64, -67, -67]
        previous = [{"rssi_dbm": value, "vibration_score": 80.0} for value in ([-58] * 20 + values)]
        _baseline, _score, _level, candidate = _score_reading(WifiReading(-63.0, None, None, None, None, None), previous)
        self.assertTrue(candidate)

    @patch("wifi_radar_collector.datetime")
    def test_output_omits_network_identifiers(self, mocked_datetime: object) -> None:
        mocked_datetime.now.return_value.astimezone.return_value.isoformat.return_value = "2026-01-01T00:00:00+00:00"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "radar.json"
            payload = collect_once(path, lambda: WifiReading(-60.0, None, None, None, None, None), "test", 1.0)
            serialized = json.dumps(payload).lower()
            self.assertNotIn("ssid", payload["current"])
            self.assertNotIn("bssid", payload["current"])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
