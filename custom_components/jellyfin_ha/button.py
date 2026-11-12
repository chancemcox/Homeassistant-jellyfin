"""Button platform for Jellyfin."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import JellyfinApiClient
from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator
from .entity import JellyfinEntity


@dataclass(frozen=True, kw_only=True)
class JellyfinButtonEntityDescription(ButtonEntityDescription):
    """Describes a Jellyfin button."""

    press_fn: Callable[[JellyfinApiClient], Awaitable[None]]


BUTTON_TYPES: tuple[JellyfinButtonEntityDescription, ...] = (
    JellyfinButtonEntityDescription(
        key="scan_libraries",
        translation_key="scan_libraries",
        icon="mdi:database-refresh",
        press_fn=lambda api: api.refresh_library(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin buttons from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        JellyfinButton(coordinator, description) for description in BUTTON_TYPES
    )


class JellyfinButton(JellyfinEntity, ButtonEntity):
    """Representation of a Jellyfin button."""

    entity_description: JellyfinButtonEntityDescription

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        description: JellyfinButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.server_id}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator.api)
        await self.coordinator.async_request_refresh()
