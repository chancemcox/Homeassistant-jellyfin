"""Unit tests for the Jellyfin API client helpers."""

from __future__ import annotations

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


def test_host_strips_trailing_slash() -> None:
    """Host URLs should not keep a trailing slash."""
    session = MagicMock()
    client = JellyfinApiClient(session, "http://jellyfin.local:8096/", "token")
    assert client.host == "http://jellyfin.local:8096"


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
