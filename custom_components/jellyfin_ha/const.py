"""Constants for the Jellyfin integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "jellyfin_ha"
DEFAULT_NAME: Final = "Jellyfin"
DEFAULT_PORT: Final = 8096
DEFAULT_SCAN_INTERVAL: Final = 30

CONF_API_KEY: Final = "api_key"

ATTR_ITEM_ID: Final = "item_id"
ATTR_SESSION_ID: Final = "session_id"

PLATFORMS: Final = [
    "binary_sensor",
    "button",
    "media_player",
    "sensor",
]

UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
