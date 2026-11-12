"""Diagnostics support for Jellyfin."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .coordinator import JellyfinConfigEntry

TO_REDACT = {CONF_API_KEY, "AccessToken", "api_key"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: JellyfinConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}

    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "domain": entry.domain,
                "data": {
                    CONF_URL: entry.data.get(CONF_URL),
                    "device_id": entry.data.get("device_id"),
                },
            },
            TO_REDACT,
        ),
        "server": {
            "id": coordinator.server_id,
            "name": coordinator.server_name,
            "version": coordinator.server_version,
        },
        "stats": data.get("stats"),
        "item_counts": data.get("item_counts"),
        "session_count": len(data.get("sessions", {})),
        "library_names": [lib.get("Name") for lib in data.get("libraries", [])],
    }
