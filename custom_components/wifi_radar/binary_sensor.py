"""Binary sensors for Wi-Fi Radar."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WifiRadarCoordinator
from .entity import WifiRadarEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the passage binary sensor."""
    coordinator: WifiRadarCoordinator = entry.runtime_data
    async_add_entities([WifiRadarPassageBinarySensor(coordinator, entry)])


class WifiRadarPassageBinarySensor(WifiRadarEntity, BinarySensorEntity):
    """Represent a merged passage candidate session."""

    _attr_translation_key = "passage"
    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, coordinator: WifiRadarCoordinator, entry: ConfigEntry) -> None:
        """Initialize the passage sensor."""
        super().__init__(coordinator, entry, "passage")

    @property
    def is_on(self) -> bool:
        """Return whether a passage session is active."""
        return self.coordinator.data.passage
