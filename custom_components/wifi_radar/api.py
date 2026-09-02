"""HTTP client and data model for a Wi-Fi Radar bridge."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from aiohttp import ClientError, ClientResponseError, ClientSession
from async_timeout import timeout

from .const import API_STATE_PATH, REQUEST_TIMEOUT_SECONDS


class WifiRadarApiError(Exception):
    """Base exception for Wi-Fi Radar API errors."""


class WifiRadarAuthError(WifiRadarApiError):
    """Raised when the bridge rejects the API key."""


class WifiRadarConnectionError(WifiRadarApiError):
    """Raised when the bridge cannot be reached."""


class WifiRadarDataError(WifiRadarApiError):
    """Raised when the bridge response is invalid."""


@dataclass(frozen=True, slots=True)
class WifiRadarState:
    """Normalized state returned by the bridge."""

    rssi: float
    score: float
    status: str
    passage: bool
    updated_at: str | None
    last_passage_duration: float | None


def event_filtered_state(
    previous: WifiRadarState | None,
    current: WifiRadarState,
) -> WifiRadarState:
    """Publish only motion events and availability transitions.

    The bridge is still polled for health, but quiet RSSI/score jitter must not
    generate a new Home Assistant state every scan interval. A completed
    passage is published once so the binary sensor can turn off and the final
    duration can be recorded.
    """
    if previous is None:
        return current
    if current.status == "stale" or previous.status == "stale":
        return current
    if current.passage or previous.passage:
        return current
    if current.last_passage_duration != previous.last_passage_duration:
        return current
    return previous


def normalize_bridge_url(value: str) -> str:
    """Validate and normalize an HTTP(S) bridge base URL."""
    candidate = value.strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Bridge URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Bridge URL must not contain credentials, query, or fragment")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _as_float(value: Any, field: str) -> float:
    """Convert a finite numeric value to float."""
    if isinstance(value, bool):
        raise WifiRadarDataError(f"{field} must be numeric")
    try:
        result = float(value)
    except (TypeError, ValueError) as err:
        raise WifiRadarDataError(f"{field} must be numeric") from err
    if result != result or result in {float("inf"), float("-inf")}:
        raise WifiRadarDataError(f"{field} must be finite")
    return result


def _as_dict(value: Any, field: str) -> dict[str, Any]:
    """Require a JSON object."""
    if not isinstance(value, dict):
        raise WifiRadarDataError(f"{field} must be a JSON object")
    return value


def _derive_status(available: bool, current: dict[str, Any], active: bool) -> str:
    """Map the bridge snapshot to Home Assistant's stable status vocabulary."""
    if not available:
        return "stale"
    if active:
        return "moving"
    motion_level = str(current.get("motion_level", "stable")).strip().lower()
    return {
        "calibrating": "calibrating",
        "quiet": "stable",
        "low": "watch",
        "medium": "watch",
        "high": "watch",
        "stable": "stable",
        "watch": "watch",
        "candidate": "watch",
        "moving": "moving",
    }.get(motion_level, "watch")


def _parse_updated_at(payload: dict[str, Any], current: dict[str, Any]) -> str | None:
    """Validate an optional ISO 8601 update timestamp."""
    value = payload.get("source_updated_at", payload.get("updated_at", current.get("timestamp")))
    if value is None:
        return None
    if not isinstance(value, str):
        raise WifiRadarDataError("updated_at must be a string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise WifiRadarDataError("updated_at must be ISO 8601") from err
    return value


def _parse_duration(passage: dict[str, Any]) -> float | None:
    """Read the optional finalized passage duration."""
    last = passage.get("last")
    if last is None:
        return None
    last_object = _as_dict(last, "passage.last")
    value = last_object.get("duration_seconds")
    if value is None:
        return None
    duration = _as_float(value, "passage.last.duration_seconds")
    if duration < 0:
        raise WifiRadarDataError("passage.last.duration_seconds must not be negative")
    return duration


def parse_state(payload: Any) -> WifiRadarState:
    """Validate and normalize the bridge's nested snapshot response."""
    root = _as_dict(payload, "response")
    current = _as_dict(root.get("current"), "current")
    passage = _as_dict(root.get("passage"), "passage")
    available = root.get("available")
    active = passage.get("active")
    if not isinstance(available, bool):
        raise WifiRadarDataError("available must be boolean")
    if not isinstance(active, bool):
        raise WifiRadarDataError("passage.active must be boolean")

    return WifiRadarState(
        rssi=_as_float(current.get("rssi_dbm"), "current.rssi_dbm"),
        score=_as_float(
            current.get("vibration_score"), "current.vibration_score"
        ),
        status=_derive_status(available, current, active),
        passage=active,
        updated_at=_parse_updated_at(root, current),
        last_passage_duration=_parse_duration(passage),
    )


class WifiRadarApiClient:
    """Small authenticated client for the Wi-Fi Radar bridge."""

    def __init__(self, session: ClientSession, bridge_url: str, api_key: str) -> None:
        """Initialize the client without logging credentials."""
        self._session = session
        self._state_url = f"{normalize_bridge_url(bridge_url)}{API_STATE_PATH}"
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def async_get_state(self) -> WifiRadarState:
        """Fetch the latest bridge state."""
        try:
            async with timeout(REQUEST_TIMEOUT_SECONDS):
                response = await self._session.get(
                    self._state_url,
                    headers=self._headers,
                )
                if response.status in {401, 403}:
                    raise WifiRadarAuthError("Authentication failed")
                response.raise_for_status()
                payload = await response.json(content_type=None)
        except WifiRadarAuthError:
            raise
        except (ClientResponseError, ClientError, TimeoutError) as err:
            raise WifiRadarConnectionError("Unable to reach Wi-Fi Radar bridge") from err
        except ValueError as err:
            raise WifiRadarDataError("Bridge returned invalid JSON") from err

        return parse_state(payload)
