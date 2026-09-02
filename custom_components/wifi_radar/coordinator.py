"""Data update coordinator for Wi-Fi Radar."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    WifiRadarApiClient,
    WifiRadarApiError,
    WifiRadarState,
    event_filtered_state,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class WifiRadarCoordinator(DataUpdateCoordinator[WifiRadarState]):
    """Coordinate one poll for every Wi-Fi Radar entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WifiRadarApiClient,
        scan_interval: int,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self.client = client
        self._published_state: WifiRadarState | None = None

    async def _async_update_data(self) -> WifiRadarState:
        """Fetch the latest bridge snapshot."""
        try:
            current = await self.client.async_get_state()
        except WifiRadarApiError as err:
            raise UpdateFailed(str(err)) from err
        self._published_state = event_filtered_state(self._published_state, current)
        return self._published_state
