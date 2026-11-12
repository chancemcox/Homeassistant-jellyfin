"""Config flow for Jellyfin."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    JellyfinApiClient,
    JellyfinAuthError,
    JellyfinConnectionError,
)
from .const import CONF_API_KEY, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://jellyfin.local:8096"): str,
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input and return info for the config entry."""
    session = async_get_clientsession(hass)
    device_id = data.get("device_id") or str(uuid4())
    client = JellyfinApiClient(
        session=session,
        host=data[CONF_URL].rstrip("/"),
        api_key=data[CONF_API_KEY],
        device_id=device_id,
    )
    info = await client.async_validate()
    return {
        "title": data.get(CONF_NAME) or info.get("ServerName") or DEFAULT_NAME,
        "server_id": info.get("Id"),
        "server_name": info.get("ServerName"),
        "version": info.get("Version"),
        "device_id": device_id,
    }


class JellyfinConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jellyfin."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            user_input[CONF_URL] = url

            try:
                info = await validate_input(self.hass, user_input)
            except JellyfinConnectionError:
                errors["base"] = "cannot_connect"
            except JellyfinAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during Jellyfin setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["server_id"])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=info["title"],
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                        "device_id": info["device_id"],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the API key is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt for a replacement API key and update the existing entry."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            data = {
                CONF_URL: reauth_entry.data[CONF_URL],
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_NAME: reauth_entry.data.get(CONF_NAME, DEFAULT_NAME),
                "device_id": reauth_entry.data.get("device_id"),
            }
            try:
                info = await validate_input(self.hass, data)
            except JellyfinConnectionError:
                errors["base"] = "cannot_connect"
            except JellyfinAuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during Jellyfin reauth")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info["server_id"])
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={
                "url": reauth_entry.data.get(CONF_URL, ""),
                "name": reauth_entry.title,
            },
            errors=errors,
        )
