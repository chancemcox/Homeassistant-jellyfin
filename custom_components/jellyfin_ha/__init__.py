"""The Jellyfin Home Assistant integration."""

from __future__ import annotations

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    JellyfinApiClient,
    JellyfinAuthError,
    JellyfinConnectionError,
)
from .const import CONF_API_KEY, DEFAULT_NAME, DOMAIN, PLATFORMS
from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> bool:
    """Set up Jellyfin from a config entry."""
    session = async_get_clientsession(hass)
    api = JellyfinApiClient(
        session=session,
        host=entry.data[CONF_URL],
        api_key=entry.data[CONF_API_KEY],
        device_id=entry.data.get("device_id"),
    )

    try:
        system_info = await api.async_validate()
    except JellyfinAuthError as err:
        raise ConfigEntryAuthFailed("Invalid Jellyfin API key") from err
    except JellyfinConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = JellyfinDataUpdateCoordinator(hass, entry, api, system_info)
    await coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.server_id)},
        manufacturer=DEFAULT_NAME,
        name=coordinator.server_name,
        sw_version=coordinator.server_version,
        model="Jellyfin Server",
        configuration_url=entry.data[CONF_URL],
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JellyfinConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: JellyfinConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Remove a device when it is no longer associated with the integration."""
    coordinator = config_entry.runtime_data
    return not device_entry.identifiers.intersection(
        {
            (DOMAIN, coordinator.server_id),
            *((DOMAIN, device_id) for device_id in coordinator.device_ids),
        }
    )
