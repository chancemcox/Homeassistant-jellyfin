"""Diagnostics support for Jellyfin."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .coordinator import JellyfinConfigEntry

TO_REDACT = {
    CONF_API_KEY,
    CONF_URL,
    CONF_NAME,
    "AccessToken",
    "api_key",
    "title",
    "device_id",
    "id",
    "name",
    "library_names",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: JellyfinConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}

    return async_redact_data(
        {
            "entry": {
                "title": entry.title,
                "domain": entry.domain,
                "data": {
                    CONF_URL: entry.data.get(CONF_URL),
                    "device_id": entry.data.get("device_id"),
                },
            },
            "server": {
                "id": coordinator.server_id,
                "name": coordinator.server_name,
                "version": coordinator.server_version,
            },
            "stats": data.get("stats"),
            "item_counts": data.get("item_counts"),
            "session_count": len(data.get("sessions", {})),
            "library_count": len(data.get("libraries", [])),
        },
        TO_REDACT,
    )
