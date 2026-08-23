"""Diagnostics support for Wi-Fi Radar."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, CONF_BRIDGE_URL
from .coordinator import WifiRadarCoordinator

TO_REDACT = {CONF_API_KEY, CONF_BRIDGE_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics with credentials and local addresses removed."""
    coordinator: WifiRadarCoordinator = entry.runtime_data
    entry_data = {
        "title": entry.title,
        "data": dict(entry.data),
        "options": dict(entry.options),
    }
    return {
        "config_entry": async_redact_data(entry_data, TO_REDACT),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "data": asdict(coordinator.data),
        },
    }
