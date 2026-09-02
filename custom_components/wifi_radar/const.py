"""Constants for the Wi-Fi Radar integration."""

from typing import Final

DOMAIN: Final = "wifi_radar"
VERSION: Final = "0.3.0"

CONF_BRIDGE_URL: Final = "bridge_url"
CONF_API_KEY: Final = "api_key"
CONF_NAME: Final = "name"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_NAME: Final = "Wi-Fi Radar"
DEFAULT_SCAN_INTERVAL: Final = 2
MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 60

API_STATE_PATH: Final = "/api/v1/state"
REQUEST_TIMEOUT_SECONDS: Final = 10

PLATFORMS: Final = ["binary_sensor", "sensor"]
