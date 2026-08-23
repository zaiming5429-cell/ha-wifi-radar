"""Data update coordinator for Wi-Fi Radar."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WifiRadarApiClient, WifiRadarApiError, WifiRadarState
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
        )
        self.client = client

    async def _async_update_data(self) -> WifiRadarState:
        """Fetch the latest bridge snapshot."""
        try:
            return await self.client.async_get_state()
        except WifiRadarApiError as err:
            raise UpdateFailed(str(err)) from err
