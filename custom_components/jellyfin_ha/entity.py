"""Base entity for Jellyfin."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import JellyfinDataUpdateCoordinator


class JellyfinEntity(CoordinatorEntity[JellyfinDataUpdateCoordinator]):
    """Base class for Jellyfin entities attached to the server device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: JellyfinDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.server_id)},
            manufacturer=DEFAULT_NAME,
            name=coordinator.server_name,
            sw_version=coordinator.server_version,
            model="Jellyfin Server",
            configuration_url=coordinator.api.host,
        )
