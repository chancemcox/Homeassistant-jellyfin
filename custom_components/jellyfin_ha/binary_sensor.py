"""Binary sensor platform for Jellyfin."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator
from .entity import JellyfinEntity


@dataclass(frozen=True, kw_only=True)
class JellyfinBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Jellyfin binary sensor."""

    is_on_fn: Callable[[dict[str, Any]], bool]


BINARY_SENSOR_TYPES: tuple[JellyfinBinarySensorEntityDescription, ...] = (
    JellyfinBinarySensorEntityDescription(
        key="server_online",
        translation_key="server_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: bool(data.get("system")),
    ),
    JellyfinBinarySensorEntityDescription(
        key="someone_watching",
        translation_key="someone_watching",
        icon="mdi:play-circle",
        is_on_fn=lambda data: data.get("stats", {}).get("watching_count", 0) > 0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin binary sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        JellyfinBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
    )


class JellyfinBinarySensor(JellyfinEntity, BinarySensorEntity):
    """Representation of a Jellyfin binary sensor."""

    entity_description: JellyfinBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        description: JellyfinBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.server_id}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
