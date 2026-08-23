"""Config flow for Wi-Fi Radar."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    WifiRadarApiClient,
    WifiRadarAuthError,
    WifiRadarConnectionError,
    WifiRadarDataError,
    normalize_bridge_url,
)
from .const import (
    CONF_API_KEY,
    CONF_BRIDGE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build a config schema with safe defaults."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_BRIDGE_URL,
                default=defaults.get(CONF_BRIDGE_URL, "http://wifi-radar-bridge.local:8080"),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Required(CONF_API_KEY): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                CONF_NAME,
                default=defaults.get(CONF_NAME, DEFAULT_NAME),
            ): TextSelector(),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


class WifiRadarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Wi-Fi Radar config flow."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Set up Wi-Fi Radar through the UI."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                bridge_url = normalize_bridge_url(user_input[CONF_BRIDGE_URL])
                api_key = str(user_input[CONF_API_KEY]).strip()
                name = str(user_input[CONF_NAME]).strip()
                scan_interval = int(user_input[CONF_SCAN_INTERVAL])
                if not api_key or not name:
                    raise ValueError

                await WifiRadarApiClient(
                    async_get_clientsession(self.hass), bridge_url, api_key
                ).async_get_state()
            except WifiRadarAuthError:
                errors["base"] = "invalid_auth"
            except WifiRadarConnectionError:
                errors["base"] = "cannot_connect"
            except (WifiRadarDataError, ValueError, TypeError, KeyError):
                errors["base"] = "invalid_data"
            else:
                await self.async_set_unique_id(bridge_url.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_BRIDGE_URL: bridge_url,
                        CONF_API_KEY: api_key,
                        CONF_NAME: name,
                        CONF_SCAN_INTERVAL: scan_interval,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )
