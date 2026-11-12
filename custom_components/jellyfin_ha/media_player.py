"""Media player platform for Jellyfin sessions."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin media players from a config entry."""
    coordinator = entry.runtime_data
    known_players: dict[str, JellyfinMediaPlayer] = {}

    @callback
    def handle_coordinator_update() -> None:
        """Add or refresh media players for active clients."""
        new_entities: list[JellyfinMediaPlayer] = []
        active_keys = set(coordinator.data.get("sessions", {}))

        for client_key, session in coordinator.data.get("sessions", {}).items():
            if client_key in known_players:
                known_players[client_key].update_session(session)
                continue
            if client_key in coordinator.session_ids:
                continue
            _LOGGER.debug("Creating media player for client %s", client_key)
            entity = JellyfinMediaPlayer(coordinator, client_key, session)
            known_players[client_key] = entity
            coordinator.session_ids.add(client_key)
            new_entities.append(entity)

        # Drop tracking for clients that no longer have a persistent device id
        # and whose session-only key has disappeared, so a later reconnect with
        # a new session id can create a fresh entity instead of leaving orphans
        # forever in session_ids. Device-backed keys stay registered.
        stale_session_keys = [
            key
            for key in list(coordinator.session_ids)
            if key not in active_keys and key not in coordinator.device_ids
        ]
        for key in stale_session_keys:
            coordinator.session_ids.discard(key)
            known_players.pop(key, None)

        if new_entities:
            async_add_entities(new_entities)

    handle_coordinator_update()
    entry.async_on_unload(coordinator.async_add_listener(handle_coordinator_update))


class JellyfinMediaPlayer(
    CoordinatorEntity[JellyfinDataUpdateCoordinator], MediaPlayerEntity
):
    """Representation of a Jellyfin client session as a media player."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        client_key: str,
        session: dict[str, Any],
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self.client_key = client_key
        self._session: dict[str, Any] = session
        self.session_id: str = session.get("Id") or client_key
        # Prefer DeviceId so reconnects keep a stable entity registry identity.
        self._attr_unique_id = f"{coordinator.server_id}_{client_key}"
        device_name = (
            session.get("DeviceName") or session.get("Client") or "Jellyfin Client"
        )
        device_id = session.get("DeviceId") or client_key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            via_device=(DOMAIN, coordinator.server_id),
            manufacturer=session.get("Client") or DEFAULT_NAME,
            name=device_name,
            model=session.get("ApplicationVersion"),
        )

    @callback
    def update_session(self, session: dict[str, Any]) -> None:
        """Refresh the active session id when a client reconnects."""
        self._session = session
        if session_id := session.get("Id"):
            self.session_id = session_id

    @property
    def available(self) -> bool:
        """Return True if the client still has an active session."""
        live = self.coordinator.data.get("sessions", {}).get(self.client_key)
        if live is not None:
            self._session = live
            if session_id := live.get("Id"):
                self.session_id = session_id
        return live is not None and super().available

    @property
    def name(self) -> str | None:
        """Return the name of the media player."""
        session = self._session
        user = session.get("UserName") or "Unknown"
        device = session.get("DeviceName") or session.get("Client") or "Client"
        return f"{user} · {device}"

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the media player."""
        if not self.available:
            return MediaPlayerState.OFF
        now_playing = self._session.get("NowPlayingItem")
        if not now_playing:
            return MediaPlayerState.IDLE
        play_state = self._session.get("PlayState") or {}
        if play_state.get("IsPaused"):
            return MediaPlayerState.PAUSED
        return MediaPlayerState.PLAYING

    @property
    def media_content_id(self) -> str | None:
        """Return the content ID of current playing media."""
        item = self._session.get("NowPlayingItem") or {}
        return item.get("Id")

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Return the content type of current playing media."""
        item = self._session.get("NowPlayingItem") or {}
        media_type = item.get("Type")
        mapping = {
            "Movie": MediaType.MOVIE,
            "Episode": MediaType.TVSHOW,
            "Audio": MediaType.MUSIC,
            "MusicVideo": MediaType.MUSIC,
            "Trailer": MediaType.VIDEO,
            "Video": MediaType.VIDEO,
        }
        return mapping.get(media_type, media_type)

    @property
    def media_title(self) -> str | None:
        """Return the title of current playing media."""
        item = self._session.get("NowPlayingItem") or {}
        if item.get("Type") == "Episode":
            series = item.get("SeriesName")
            name = item.get("Name")
            if series and name:
                return f"{series} - {name}"
        return item.get("Name")

    @property
    def media_series_title(self) -> str | None:
        """Return the series title."""
        item = self._session.get("NowPlayingItem") or {}
        return item.get("SeriesName")

    @property
    def media_season(self) -> str | None:
        """Return the season."""
        item = self._session.get("NowPlayingItem") or {}
        season = item.get("ParentIndexNumber")
        return str(season) if season is not None else None

    @property
    def media_episode(self) -> str | None:
        """Return the episode."""
        item = self._session.get("NowPlayingItem") or {}
        episode = item.get("IndexNumber")
        return str(episode) if episode is not None else None

    @property
    def media_album_name(self) -> str | None:
        """Return the album name."""
        item = self._session.get("NowPlayingItem") or {}
        return item.get("Album")

    @property
    def media_artist(self) -> str | None:
        """Return the artist."""
        item = self._session.get("NowPlayingItem") or {}
        artists = item.get("Artists") or []
        return artists[0] if artists else item.get("AlbumArtist")

    @property
    def media_duration(self) -> int | None:
        """Return the duration of current playing media in seconds."""
        item = self._session.get("NowPlayingItem") or {}
        ticks = item.get("RunTimeTicks")
        return int(ticks / 10_000_000) if ticks else None

    @property
    def media_position(self) -> int | None:
        """Return the position of current playing media in seconds."""
        play_state = self._session.get("PlayState") or {}
        ticks = play_state.get("PositionTicks")
        return int(ticks / 10_000_000) if ticks is not None else None

    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return when the position was last reported by Jellyfin."""
        if self.media_position is None:
            return None
        check_in = self._session.get("LastPlaybackCheckIn")
        if not check_in:
            return dt_util.utcnow()
        parsed = dt_util.parse_datetime(check_in)
        return parsed or dt_util.utcnow()

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of current playing media."""
        item = self._session.get("NowPlayingItem") or {}
        primary_tag = (item.get("ImageTags") or {}).get("Primary")
        if primary_tag and (item_id := item.get("Id")):
            return (
                f"{self.coordinator.api.host}/Items/{item_id}/Images/Primary"
                f"?tag={primary_tag}"
            )

        album_tag = item.get("AlbumPrimaryImageTag")
        album_id = item.get("AlbumId")
        if album_tag and album_id:
            return (
                f"{self.coordinator.api.host}/Items/{album_id}/Images/Primary"
                f"?tag={album_tag}"
            )
        return None

    @property
    def volume_level(self) -> float | None:
        """Return the volume level of the media player (0..1)."""
        play_state = self._session.get("PlayState") or {}
        volume = play_state.get("VolumeLevel")
        return volume / 100 if volume is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return true if volume is muted."""
        play_state = self._session.get("PlayState") or {}
        return play_state.get("IsMuted")

    @property
    def app_name(self) -> str | None:
        """Return the current client application name."""
        return self._session.get("Client")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        play_state = self._session.get("PlayState") or {}
        return {
            "user_name": self._session.get("UserName"),
            "client": self._session.get("Client"),
            "device_name": self._session.get("DeviceName"),
            "play_method": play_state.get("PlayMethod"),
            "session_id": self.session_id,
        }

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        commands: list[str] = self._session.get("SupportedCommands") or []
        controllable = self._session.get("SupportsMediaControl", False)
        features = MediaPlayerEntityFeature(0)

        if controllable:
            features |= (
                MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.SEEK
                | MediaPlayerEntityFeature.PLAY_MEDIA
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
            )

        if "Mute" in commands or "Unmute" in commands:
            features |= MediaPlayerEntityFeature.VOLUME_MUTE

        if "SetVolume" in commands:
            features |= MediaPlayerEntityFeature.VOLUME_SET

        return features

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.coordinator.api.remote_unpause(self.session_id)
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.coordinator.api.remote_pause(self.session_id)
        await self.coordinator.async_request_refresh()

    async def async_media_play_pause(self) -> None:
        """Send play/pause toggle command."""
        await self.coordinator.api.remote_play_pause(self.session_id)
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.coordinator.api.remote_stop(self.session_id)
        await self.coordinator.async_request_refresh()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command (position in seconds)."""
        await self.coordinator.api.remote_seek(
            self.session_id, int(position * 10_000_000)
        )
        await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.coordinator.api.remote_next(self.session_id)
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.coordinator.api.remote_previous(self.session_id)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.api.remote_set_volume(self.session_id, int(volume * 100))
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the volume."""
        if mute:
            await self.coordinator.api.remote_mute(self.session_id)
        else:
            await self.coordinator.api.remote_unmute(self.session_id)
        await self.coordinator.async_request_refresh()

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media by Jellyfin item ID."""
        await self.coordinator.api.remote_play_media(self.session_id, [media_id])
        await self.coordinator.async_request_refresh()
