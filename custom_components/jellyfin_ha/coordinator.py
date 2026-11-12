"""Data update coordinator for Jellyfin."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import JellyfinApiClient, JellyfinApiError, JellyfinAuthError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type JellyfinConfigEntry = ConfigEntry[JellyfinDataUpdateCoordinator]


class JellyfinDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Jellyfin for system, library, and session state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: JellyfinConfigEntry,
        api: JellyfinApiClient,
        system_info: dict[str, Any],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api
        self.entry = entry
        self.system_info = system_info
        self.server_id: str = system_info.get("Id", entry.entry_id)
        self.server_name: str = system_info.get("ServerName", "Jellyfin")
        self.server_version: str = system_info.get("Version", "unknown")
        # Persistent client keys currently represented by media player entities.
        self.session_ids: set[str] = set()
        self.device_ids: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data from Jellyfin."""
        try:
            system_info = await self.api.get_system_info()
            sessions = await self.api.get_sessions()
            item_counts = await self.api.get_item_counts()
            users = await self.api.get_users()
            libraries = await self.api.get_libraries()
        except JellyfinAuthError as err:
            raise ConfigEntryAuthFailed("Invalid Jellyfin API key") from err
        except JellyfinApiError as err:
            raise UpdateFailed(f"Error communicating with Jellyfin: {err}") from err

        self.system_info = system_info
        self.server_name = system_info.get("ServerName", self.server_name)
        self.server_version = system_info.get("Version", self.server_version)

        # Index sessions by a stable client key for media players.
        # Prefer DeviceId so reconnects reuse the same entity.
        session_map: dict[str, dict[str, Any]] = {}
        current_device_ids: set[str] = set()
        watching = 0
        transcoding = 0
        for session in sessions:
            session_id = session.get("Id")
            if not session_id:
                continue
            # Skip our own Home Assistant client session
            if session.get("DeviceId") == self.entry.data.get("device_id"):
                continue
            client_key = session.get("DeviceId") or session_id
            session_map[client_key] = session
            if session.get("DeviceId"):
                current_device_ids.add(session["DeviceId"])
            if session.get("NowPlayingItem"):
                watching += 1
            if session.get("PlayState", {}).get("PlayMethod") == "Transcode":
                transcoding += 1

        self.device_ids = current_device_ids

        return {
            "system": system_info,
            "sessions": session_map,
            "item_counts": item_counts,
            "users": users,
            "libraries": libraries,
            "stats": {
                "session_count": len(session_map),
                "watching_count": watching,
                "transcoding_count": transcoding,
                "user_count": len(users),
                "library_count": len(libraries),
            },
        }
