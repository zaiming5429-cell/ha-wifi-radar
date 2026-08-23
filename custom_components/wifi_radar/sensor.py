"""Sensors for Wi-Fi Radar."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import WifiRadarState
from .coordinator import WifiRadarCoordinator
from .entity import WifiRadarEntity


@dataclass(frozen=True, kw_only=True)
class WifiRadarSensorDescription(SensorEntityDescription):
    """Describe a Wi-Fi Radar sensor."""

    value_fn: Callable[[WifiRadarState], Any]


SENSORS: tuple[WifiRadarSensorDescription, ...] = (
    WifiRadarSensorDescription(
        key="rssi",
        translation_key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement="dBm",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda state: state.rssi,
    ),
    WifiRadarSensorDescription(
        key="score",
        translation_key="score",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda state: state.score,
    ),
    WifiRadarSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["calibrating", "stable", "watch", "moving", "stale"],
        value_fn=lambda state: state.status,
    ),
    WifiRadarSensorDescription(
        key="last_passage_duration",
        translation_key="last_passage_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda state: state.last_passage_duration,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wi-Fi Radar sensors."""
    coordinator: WifiRadarCoordinator = entry.runtime_data
    async_add_entities(
        WifiRadarSensor(coordinator, entry, description) for description in SENSORS
    )


class WifiRadarSensor(WifiRadarEntity, SensorEntity):
    """Represent one value from the shared bridge snapshot."""

    entity_description: WifiRadarSensorDescription

    def __init__(
        self,
        coordinator: WifiRadarCoordinator,
        entry: ConfigEntry,
        description: WifiRadarSensorDescription,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the latest native sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
