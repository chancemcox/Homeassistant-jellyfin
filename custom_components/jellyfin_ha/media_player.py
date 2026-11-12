"""Media player platform for Jellyfin sessions."""

from __future__ import annotations

import logging
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

    @callback
    def handle_coordinator_update() -> None:
        """Add a media player for each new session."""
        new_entities: list[JellyfinMediaPlayer] = []
        for session_id in coordinator.data.get("sessions", {}):
            if session_id not in coordinator.session_ids:
                _LOGGER.debug("Creating media player for session %s", session_id)
                coordinator.session_ids.add(session_id)
                new_entities.append(JellyfinMediaPlayer(coordinator, session_id))
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
        session_id: str,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self.session_id = session_id
        self._attr_unique_id = f"{coordinator.server_id}_{session_id}"
        session = self._session
        device_name = (
            (session or {}).get("DeviceName")
            or (session or {}).get("Client")
            or "Jellyfin Client"
        )
        device_id = (session or {}).get("DeviceId") or session_id
        coordinator.device_ids.add(device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            via_device=(DOMAIN, coordinator.server_id),
            manufacturer=(session or {}).get("Client") or DEFAULT_NAME,
            name=device_name,
            model=(session or {}).get("ApplicationVersion"),
        )

    @property
    def _session(self) -> dict[str, Any] | None:
        """Return the current session data, if available."""
        return self.coordinator.data.get("sessions", {}).get(self.session_id)

    @property
    def available(self) -> bool:
        """Return True if the session is still active."""
        return self._session is not None and super().available

    @property
    def name(self) -> str | None:
        """Return the name of the media player."""
        session = self._session
        if not session:
            return None
        user = session.get("UserName") or "Unknown"
        device = session.get("DeviceName") or session.get("Client") or "Client"
        return f"{user} · {device}"

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the media player."""
        session = self._session
        if not session:
            return MediaPlayerState.OFF
        now_playing = session.get("NowPlayingItem")
        if not now_playing:
            return MediaPlayerState.IDLE
        play_state = session.get("PlayState") or {}
        if play_state.get("IsPaused"):
            return MediaPlayerState.PAUSED
        return MediaPlayerState.PLAYING

    @property
    def media_content_id(self) -> str | None:
        """Return the content ID of current playing media."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        return item.get("Id")

    @property
    def media_content_type(self) -> MediaType | str | None:
        """Return the content type of current playing media."""
        item = (self._session or {}).get("NowPlayingItem") or {}
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
        item = (self._session or {}).get("NowPlayingItem") or {}
        if item.get("Type") == "Episode":
            series = item.get("SeriesName")
            name = item.get("Name")
            if series and name:
                return f"{series} - {name}"
        return item.get("Name")

    @property
    def media_series_title(self) -> str | None:
        """Return the series title."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        return item.get("SeriesName")

    @property
    def media_season(self) -> str | None:
        """Return the season."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        season = item.get("ParentIndexNumber")
        return str(season) if season is not None else None

    @property
    def media_episode(self) -> str | None:
        """Return the episode."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        episode = item.get("IndexNumber")
        return str(episode) if episode is not None else None

    @property
    def media_album_name(self) -> str | None:
        """Return the album name."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        return item.get("Album")

    @property
    def media_artist(self) -> str | None:
        """Return the artist."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        artists = item.get("Artists") or []
        return artists[0] if artists else item.get("AlbumArtist")

    @property
    def media_duration(self) -> int | None:
        """Return the duration of current playing media in seconds."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        ticks = item.get("RunTimeTicks")
        return int(ticks / 10_000_000) if ticks else None

    @property
    def media_position(self) -> int | None:
        """Return the position of current playing media in seconds."""
        play_state = (self._session or {}).get("PlayState") or {}
        ticks = play_state.get("PositionTicks")
        return int(ticks / 10_000_000) if ticks is not None else None

    @property
    def media_image_url(self) -> str | None:
        """Return the image URL of current playing media."""
        item = (self._session or {}).get("NowPlayingItem") or {}
        item_id = item.get("Id")
        if not item_id:
            return None
        tag = (item.get("ImageTags") or {}).get("Primary")
        url = f"{self.coordinator.api.host}/Items/{item_id}/Images/Primary"
        if tag:
            url = f"{url}?tag={tag}"
        return url

    @property
    def volume_level(self) -> float | None:
        """Return the volume level of the media player (0..1)."""
        play_state = (self._session or {}).get("PlayState") or {}
        volume = play_state.get("VolumeLevel")
        return volume / 100 if volume is not None else None

    @property
    def is_volume_muted(self) -> bool | None:
        """Return true if volume is muted."""
        play_state = (self._session or {}).get("PlayState") or {}
        return play_state.get("IsMuted")

    @property
    def app_name(self) -> str | None:
        """Return the current client application name."""
        return (self._session or {}).get("Client")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        session = self._session or {}
        play_state = session.get("PlayState") or {}
        return {
            "user_name": session.get("UserName"),
            "client": session.get("Client"),
            "device_name": session.get("DeviceName"),
            "play_method": play_state.get("PlayMethod"),
            "session_id": self.session_id,
        }

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        session = self._session or {}
        commands: list[str] = session.get("SupportedCommands") or []
        controllable = session.get("SupportsMediaControl", False)
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
