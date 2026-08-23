"""Base entity for Wi-Fi Radar."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BRIDGE_URL, DOMAIN, VERSION
from .coordinator import WifiRadarCoordinator


class WifiRadarEntity(CoordinatorEntity[WifiRadarCoordinator]):
    """Base class shared by Wi-Fi Radar entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WifiRadarCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize an entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Wi-Fi Radar",
            model="RSSI Passage Bridge",
            sw_version=VERSION,
            configuration_url=entry.data[CONF_BRIDGE_URL],
        )

    @property
    def available(self) -> bool:
        """Return unavailable when polling fails or the bridge marks data stale."""
        return super().available and self.coordinator.data.status != "stale"
