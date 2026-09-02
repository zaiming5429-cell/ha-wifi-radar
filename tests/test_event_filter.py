"""Tests for event-filtered Home Assistant state publication."""

from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import types
import unittest


# api.py's transport imports are not needed by these pure state-filter tests.
aiohttp_stub = types.ModuleType("aiohttp")
aiohttp_stub.ClientError = type("ClientError", (Exception,), {})
aiohttp_stub.ClientResponseError = type("ClientResponseError", (Exception,), {})
aiohttp_stub.ClientSession = object
async_timeout_stub = types.ModuleType("async_timeout")
async_timeout_stub.timeout = object
sys.modules.setdefault("aiohttp", aiohttp_stub)
sys.modules.setdefault("async_timeout", async_timeout_stub)


PACKAGE_PATH = Path(__file__).parents[1] / "custom_components" / "wifi_radar"
package = types.ModuleType("wifi_radar")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules["wifi_radar"] = package

CONST_SPEC = importlib.util.spec_from_file_location(
    "wifi_radar.const", PACKAGE_PATH / "const.py"
)
assert CONST_SPEC is not None and CONST_SPEC.loader is not None
CONST = importlib.util.module_from_spec(CONST_SPEC)
sys.modules[CONST_SPEC.name] = CONST
CONST_SPEC.loader.exec_module(CONST)

SPEC = importlib.util.spec_from_file_location("wifi_radar.api", PACKAGE_PATH / "api.py")
assert SPEC is not None and SPEC.loader is not None
API = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = API
SPEC.loader.exec_module(API)

WifiRadarState = API.WifiRadarState
event_filtered_state = API.event_filtered_state


class EventFilteredStateTest(unittest.TestCase):
    """Verify quiet samples are held and passage edges are published."""

    def setUp(self) -> None:
        self.stable = WifiRadarState(-63.0, 12.0, "stable", False, "t0", None)

    def test_quiet_jitter_is_suppressed(self) -> None:
        jitter = replace(
            self.stable,
            rssi=-60.0,
            score=28.0,
            status="watch",
            updated_at="t1",
        )
        self.assertIs(event_filtered_state(self.stable, jitter), self.stable)

    def test_active_passage_is_published(self) -> None:
        moving = replace(self.stable, score=80.0, status="moving", passage=True)
        self.assertIs(event_filtered_state(self.stable, moving), moving)

    def test_active_passage_jitter_is_suppressed(self) -> None:
        moving = replace(self.stable, score=80.0, status="moving", passage=True)
        jitter = replace(moving, rssi=-59.0, score=92.0, updated_at="t1")
        self.assertIs(event_filtered_state(moving, jitter), moving)

    def test_passage_end_is_published_once(self) -> None:
        moving = replace(self.stable, status="moving", passage=True)
        ended = replace(self.stable, last_passage_duration=9.5, updated_at="t2")
        self.assertIs(event_filtered_state(moving, ended), ended)
        jitter = replace(ended, rssi=-61.0, score=17.0, updated_at="t3")
        self.assertIs(event_filtered_state(ended, jitter), ended)


if __name__ == "__main__":
    unittest.main()
