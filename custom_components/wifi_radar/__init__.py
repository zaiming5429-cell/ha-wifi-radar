"""Wi-Fi Radar integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WifiRadarApiClient
from .const import (
    CONF_API_KEY,
    CONF_BRIDGE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import WifiRadarCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wi-Fi Radar from a config entry."""
    client = WifiRadarApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_BRIDGE_URL],
        entry.data[CONF_API_KEY],
    )
    coordinator = WifiRadarCoordinator(
        hass,
        client,
        entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Wi-Fi Radar config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
