"""Jellyfin API client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from aiohttp import ClientError, ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

TIMEOUT = ClientTimeout(total=15)
CLIENT_NAME = "Home Assistant"
CLIENT_VERSION = "1.2.1"
DEFAULT_HTTP_PORT = 8096
DEFAULT_HTTPS_PORT = 443
PORT_CONNECT_TIMEOUT = 5.0


class JellyfinApiError(Exception):
    """Base exception for Jellyfin API errors."""


class JellyfinAuthError(JellyfinApiError):
    """Raised when authentication fails."""


class JellyfinConnectionError(JellyfinApiError):
    """Raised when the server cannot be reached."""


def normalize_base_url(url: str) -> str:
    """Normalize a Jellyfin base URL and default HTTP to port 8096."""
    cleaned = url.strip().rstrip("/")
    if "://" not in cleaned:
        cleaned = f"http://{cleaned}"

    parsed = urlparse(cleaned)
    scheme = (parsed.scheme or "http").lower()
    hostname = parsed.hostname
    if not hostname:
        raise JellyfinConnectionError(f"Invalid Jellyfin URL: {url}")

    # Home Assistant Core runs in its own container. localhost/127.0.0.1 there
    # is not the HA OS host where the Jellyfin add-on publishes port 8096.
    if hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
        raise JellyfinConnectionError(
            "Do not use localhost or 127.0.0.1. From Home Assistant use the "
            "host LAN IP (for example http://192.168.2.101:8096) or the add-on "
            "hostname (for example http://fe27ebb0-jellyfin:8096)."
        )

    port = parsed.port
    if port is None:
        port = DEFAULT_HTTPS_PORT if scheme == "https" else DEFAULT_HTTP_PORT

    netloc = f"{hostname}:{port}"
    if parsed.username is not None:
        userinfo = parsed.username
        if parsed.password is not None:
            userinfo = f"{userinfo}:{parsed.password}"
        netloc = f"{userinfo}@{netloc}"

    path = parsed.path.rstrip("/") if parsed.path not in ("", "/") else ""
    return f"{scheme}://{netloc}{path}"


def parse_host_port(url: str) -> tuple[str, int]:
    """Return hostname and port for a Jellyfin base URL."""
    normalized = normalize_base_url(url)
    parsed = urlparse(normalized)
    assert parsed.hostname is not None
    assert parsed.port is not None
    return parsed.hostname, parsed.port


class JellyfinApiClient:
    """Async client for the Jellyfin REST API."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        api_key: str,
        device_id: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._host = normalize_base_url(host)
        self._api_key = api_key
        self._device_id = device_id or str(uuid4())
        self._hostname, self._port = parse_host_port(self._host)

    @property
    def host(self) -> str:
        """Return the configured host URL."""
        return self._host

    @property
    def port(self) -> int:
        """Return the Jellyfin TCP port."""
        return self._port

    def _headers(self) -> dict[str, str]:
        """Build request headers including Jellyfin auth."""
        auth = (
            f'MediaBrowser Client="{CLIENT_NAME}", '
            f'Device="Home Assistant", '
            f'DeviceId="{self._device_id}", '
            f'Version="{CLIENT_VERSION}", '
            f'Token="{self._api_key}"'
        )
        return {
            "Authorization": auth,
            "X-Emby-Token": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Perform an HTTP request against the Jellyfin server."""
        url = f"{self._host}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=TIMEOUT,
                raise_for_status=False,
            ) as response:
                if response.status in (401, 403):
                    raise JellyfinAuthError("Invalid API key or insufficient permissions")
                if response.status >= 400:
                    text = await response.text()
                    raise JellyfinApiError(
                        f"Jellyfin API error {response.status}: {text[:200]}"
                    )
                if response.status == 204 or response.content_length == 0:
                    return None
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return await response.json()
                return await response.text()
        except TimeoutError as err:
            raise JellyfinConnectionError("Timed out connecting to Jellyfin") from err
        except ClientError as err:
            raise JellyfinConnectionError(f"Error connecting to Jellyfin: {err}") from err

    async def get_system_info(self) -> dict[str, Any]:
        """Return authenticated system info."""
        data = await self._request("GET", "/System/Info")
        return data or {}

    async def async_check_port(self) -> None:
        """Verify the Jellyfin TCP port accepts connections."""
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._hostname, self._port),
                timeout=PORT_CONNECT_TIMEOUT,
            )
        except TimeoutError as err:
            raise JellyfinConnectionError(
                f"Timed out connecting to Jellyfin at {self._hostname}:{self._port}"
            ) from err
        except OSError as err:
            raise JellyfinConnectionError(
                f"Cannot connect to Jellyfin at {self._hostname}:{self._port}: {err}"
            ) from err

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        _LOGGER.debug("Jellyfin port open: %s:%s", self._hostname, self._port)

    async def get_public_info(self) -> dict[str, Any]:
        """Return public system info (no auth required for reachability)."""
        url = f"{self._host}/System/Info/Public"
        try:
            async with self._session.get(url, timeout=TIMEOUT) as response:
                if response.status >= 400:
                    raise JellyfinConnectionError(
                        f"Cannot reach Jellyfin at {self._hostname}:{self._port} "
                        f"(HTTP {response.status})"
                    )
                return await response.json()
        except TimeoutError as err:
            raise JellyfinConnectionError(
                f"Timed out reaching Jellyfin at {self._hostname}:{self._port}"
            ) from err
        except ClientError as err:
            raise JellyfinConnectionError(
                f"Cannot reach Jellyfin at {self._hostname}:{self._port}: {err}"
            ) from err

    async def get_sessions(self) -> list[dict[str, Any]]:
        """Return active sessions."""
        data = await self._request("GET", "/Sessions")
        return data or []

    async def get_item_counts(self) -> dict[str, Any]:
        """Return library item counts."""
        data = await self._request("GET", "/Items/Counts")
        return data or {}

    async def get_users(self) -> list[dict[str, Any]]:
        """Return configured users."""
        data = await self._request("GET", "/Users")
        return data or []

    async def get_libraries(self) -> list[dict[str, Any]]:
        """Return virtual folders (libraries)."""
        data = await self._request("GET", "/Library/VirtualFolders")
        return data or []

    async def refresh_library(self) -> None:
        """Trigger a full library scan."""
        await self._request("POST", "/Library/Refresh")

    async def remote_command(self, session_id: str, command: str) -> None:
        """Send a general command to a session."""
        await self._request(
            "POST",
            f"/Sessions/{session_id}/Command",
            json={"Name": command, "Arguments": {}},
        )

    async def remote_play_pause(self, session_id: str) -> None:
        """Toggle play/pause on a session."""
        await self._request("POST", f"/Sessions/{session_id}/Playing/PlayPause")

    async def remote_pause(self, session_id: str) -> None:
        """Pause playback on a session."""
        await self._request("POST", f"/Sessions/{session_id}/Playing/Pause")

    async def remote_unpause(self, session_id: str) -> None:
        """Resume playback on a session."""
        await self._request("POST", f"/Sessions/{session_id}/Playing/Unpause")

    async def remote_stop(self, session_id: str) -> None:
        """Stop playback on a session."""
        await self._request("POST", f"/Sessions/{session_id}/Playing/Stop")

    async def remote_seek(self, session_id: str, position_ticks: int) -> None:
        """Seek to a position (in ticks) on a session."""
        await self._request(
            "POST",
            f"/Sessions/{session_id}/Playing/Seek",
            params={"seekPositionTicks": position_ticks},
        )

    async def remote_next(self, session_id: str) -> None:
        """Skip to next track/item."""
        await self._request("POST", f"/Sessions/{session_id}/Playing/NextTrack")

    async def remote_previous(self, session_id: str) -> None:
        """Skip to previous track/item."""
        await self._request("POST", f"/Sessions/{session_id}/Playing/PreviousTrack")

    async def remote_set_volume(self, session_id: str, volume: int) -> None:
        """Set session volume (0-100)."""
        await self._request(
            "POST",
            f"/Sessions/{session_id}/Command",
            json={"Name": "SetVolume", "Arguments": {"Volume": str(volume)}},
        )

    async def remote_mute(self, session_id: str) -> None:
        """Mute a session."""
        await self._request(
            "POST",
            f"/Sessions/{session_id}/Command",
            json={"Name": "Mute", "Arguments": {}},
        )

    async def remote_unmute(self, session_id: str) -> None:
        """Unmute a session."""
        await self._request(
            "POST",
            f"/Sessions/{session_id}/Command",
            json={"Name": "Unmute", "Arguments": {}},
        )

    async def remote_play_media(self, session_id: str, item_ids: list[str]) -> None:
        """Play media items on a session."""
        await self._request(
            "POST",
            f"/Sessions/{session_id}/Playing",
            params={"playCommand": "PlayNow", "itemIds": ",".join(item_ids)},
        )

    async def async_validate(self) -> dict[str, Any]:
        """Validate port reachability, API reachability, and credentials."""
        await self.async_check_port()
        await self.get_public_info()
        return await self.get_system_info()
