"""Sensor platform for Jellyfin."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import JellyfinConfigEntry, JellyfinDataUpdateCoordinator
from .entity import JellyfinEntity


@dataclass(frozen=True, kw_only=True)
class JellyfinSensorEntityDescription(SensorEntityDescription):
    """Describes a Jellyfin sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _item_count(key: str) -> Callable[[dict[str, Any]], StateType]:
    return lambda data: data.get("item_counts", {}).get(key)


SENSOR_TYPES: tuple[JellyfinSensorEntityDescription, ...] = (
    JellyfinSensorEntityDescription(
        key="server_version",
        translation_key="server_version",
        icon="mdi:server",
        value_fn=lambda data: data.get("system", {}).get("Version"),
    ),
    JellyfinSensorEntityDescription(
        key="active_sessions",
        translation_key="active_sessions",
        icon="mdi:account-multiple",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("stats", {}).get("session_count", 0),
        attrs_fn=lambda data: {
            "sessions": [
                {
                    "user": s.get("UserName"),
                    "client": s.get("Client"),
                    "device": s.get("DeviceName"),
                    "playing": bool(s.get("NowPlayingItem")),
                }
                for s in data.get("sessions", {}).values()
            ]
        },
    ),
    JellyfinSensorEntityDescription(
        key="watching",
        translation_key="watching",
        icon="mdi:eye",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("stats", {}).get("watching_count", 0),
        attrs_fn=lambda data: {
            "now_playing": [
                {
                    "user": s.get("UserName"),
                    "title": (s.get("NowPlayingItem") or {}).get("Name"),
                    "type": (s.get("NowPlayingItem") or {}).get("Type"),
                    "series": (s.get("NowPlayingItem") or {}).get("SeriesName"),
                    "client": s.get("Client"),
                    "device": s.get("DeviceName"),
                    "transcoding": s.get("PlayState", {}).get("PlayMethod")
                    == "Transcode",
                }
                for s in data.get("sessions", {}).values()
                if s.get("NowPlayingItem")
            ]
        },
    ),
    JellyfinSensorEntityDescription(
        key="transcoding",
        translation_key="transcoding",
        icon="mdi:cog-transfer",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("stats", {}).get("transcoding_count", 0),
    ),
    JellyfinSensorEntityDescription(
        key="movies",
        translation_key="movies",
        icon="mdi:movie",
        state_class=SensorStateClass.TOTAL,
        value_fn=_item_count("MovieCount"),
    ),
    JellyfinSensorEntityDescription(
        key="series",
        translation_key="series",
        icon="mdi:television-classic",
        state_class=SensorStateClass.TOTAL,
        value_fn=_item_count("SeriesCount"),
    ),
    JellyfinSensorEntityDescription(
        key="episodes",
        translation_key="episodes",
        icon="mdi:filmstrip",
        state_class=SensorStateClass.TOTAL,
        value_fn=_item_count("EpisodeCount"),
    ),
    JellyfinSensorEntityDescription(
        key="songs",
        translation_key="songs",
        icon="mdi:music-note",
        state_class=SensorStateClass.TOTAL,
        value_fn=_item_count("SongCount"),
    ),
    JellyfinSensorEntityDescription(
        key="albums",
        translation_key="albums",
        icon="mdi:album",
        state_class=SensorStateClass.TOTAL,
        value_fn=_item_count("AlbumCount"),
    ),
    JellyfinSensorEntityDescription(
        key="artists",
        translation_key="artists",
        icon="mdi:account-music",
        state_class=SensorStateClass.TOTAL,
        value_fn=_item_count("ArtistCount"),
    ),
    JellyfinSensorEntityDescription(
        key="users",
        translation_key="users",
        icon="mdi:account-group",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("stats", {}).get("user_count", 0),
    ),
    JellyfinSensorEntityDescription(
        key="libraries",
        translation_key="libraries",
        icon="mdi:bookshelf",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.get("stats", {}).get("library_count", 0),
        attrs_fn=lambda data: {
            "libraries": [
                {
                    "name": lib.get("Name"),
                    "collection_type": lib.get("CollectionType"),
                }
                for lib in data.get("libraries", [])
            ]
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: JellyfinConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jellyfin sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        JellyfinSensor(coordinator, description) for description in SENSOR_TYPES
    )


class JellyfinSensor(JellyfinEntity, SensorEntity):
    """Representation of a Jellyfin sensor."""

    entity_description: JellyfinSensorEntityDescription

    def __init__(
        self,
        coordinator: JellyfinDataUpdateCoordinator,
        description: JellyfinSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.server_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return optional attributes."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
