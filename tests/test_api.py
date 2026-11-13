"""Unit tests for the Jellyfin API client helpers."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

API_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "jellyfin_ha" / "api.py"


def _load_api_module():
    """Load api.py without importing Home Assistant."""
    spec = importlib.util.spec_from_file_location("jellyfin_ha_api", API_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


api = _load_api_module()
JellyfinApiClient = api.JellyfinApiClient
JellyfinAuthError = api.JellyfinAuthError
JellyfinConnectionError = api.JellyfinConnectionError
normalize_base_url = api.normalize_base_url
parse_host_port = api.parse_host_port


def test_host_strips_trailing_slash() -> None:
    """Host URLs should not keep a trailing slash."""
    session = MagicMock()
    client = JellyfinApiClient(session, "http://jellyfin.local:8096/", "token")
    assert client.host == "http://jellyfin.local:8096"


def test_normalize_defaults_http_to_8096() -> None:
    """HTTP URLs without a port should default to Jellyfin's 8096."""
    assert normalize_base_url("http://192.168.2.101") == "http://192.168.2.101:8096"
    assert normalize_base_url("192.168.2.101") == "http://192.168.2.101:8096"
    assert parse_host_port("http://192.168.2.101") == ("192.168.2.101", 8096)


def test_normalize_preserves_explicit_port() -> None:
    """Explicit ports should be kept."""
    assert normalize_base_url("http://jellyfin.local:8920") == "http://jellyfin.local:8920"
    assert parse_host_port("https://jellyfin.example") == ("jellyfin.example", 443)


def test_normalize_rejects_loopback() -> None:
    """Loopback URLs are unreachable from the Home Assistant container."""
    with pytest.raises(JellyfinConnectionError, match="localhost|127.0.0.1|LAN IP"):
        normalize_base_url("http://127.0.0.1:8096")
    with pytest.raises(JellyfinConnectionError, match="localhost|127.0.0.1|LAN IP"):
        normalize_base_url("http://localhost:8096")


@pytest.mark.asyncio
async def test_auth_error_on_401() -> None:
    """401 responses should raise JellyfinAuthError."""
    response = MagicMock()
    response.status = 401
    response.text = AsyncMock(return_value="Unauthorized")
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.request = MagicMock(return_value=response)

    client = JellyfinApiClient(session, "http://jellyfin.local:8096", "bad-key")

    with pytest.raises(JellyfinAuthError):
        await client.get_system_info()


@pytest.mark.asyncio
async def test_connection_error_on_timeout() -> None:
    """Timeouts should raise JellyfinConnectionError."""
    session = MagicMock()

    class _TimeoutCM:
        async def __aenter__(self):
            raise TimeoutError

        async def __aexit__(self, *args):
            return None

    session.request = MagicMock(return_value=_TimeoutCM())
    client = JellyfinApiClient(session, "http://jellyfin.local:8096", "token")

    with pytest.raises(JellyfinConnectionError):
        await client.get_system_info()


@pytest.mark.asyncio
async def test_get_sessions_parses_json() -> None:
    """Successful session responses should return the JSON payload."""
    payload = [{"Id": "abc", "UserName": "demo"}]
    response = MagicMock()
    response.status = 200
    response.content_length = 10
    response.headers = {"Content-Type": "application/json"}
    response.json = AsyncMock(return_value=payload)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.request = MagicMock(return_value=response)
    client = JellyfinApiClient(session, "http://jellyfin.local:8096", "token")

    assert await client.get_sessions() == payload


def _client_for_loopback_port(session: MagicMock, port: int) -> JellyfinApiClient:
    """Build a client that targets a loopback listener (tests only)."""
    client = JellyfinApiClient(session, "http://192.168.2.101:8096", "token")
    client._hostname = "127.0.0.1"
    client._port = port
    client._host = f"http://127.0.0.1:{port}"
    return client


@pytest.mark.asyncio
async def test_check_port_succeeds_when_listening() -> None:
    """async_check_port should succeed when the TCP port is open."""
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    session = MagicMock()
    client = _client_for_loopback_port(session, port)

    try:
        await client.async_check_port()
        assert client.port == port
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_check_port_fails_when_closed() -> None:
    """async_check_port should fail clearly when nothing listens on the port."""
    # Bind then close to pick a free port that is not listening afterward.
    probe = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = probe.sockets[0].getsockname()[1]
    probe.close()
    await probe.wait_closed()

    session = MagicMock()
    client = _client_for_loopback_port(session, port)

    with pytest.raises(JellyfinConnectionError, match=str(port)):
        await client.async_check_port()


@pytest.mark.asyncio
async def test_async_validate_checks_port_before_api() -> None:
    """async_validate should refuse to continue when the port is closed."""
    probe = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
    port = probe.sockets[0].getsockname()[1]
    probe.close()
    await probe.wait_closed()

    session = MagicMock()
    client = _client_for_loopback_port(session, port)

    with pytest.raises(JellyfinConnectionError, match=str(port)):
        await client.async_validate()
    session.request.assert_not_called()
