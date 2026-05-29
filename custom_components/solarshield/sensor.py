"""Sensor platform for SolarShield HA."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_COVER_ENTITY, DOMAIN
from .coordinator import SolarShieldCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SolarShield sensor entities from a config entry."""
    coordinator: SolarShieldCoordinator = hass.data[DOMAIN][entry.entry_id]
    cover_entity = entry.data[CONF_COVER_ENTITY]

    async_add_entities([
        SolarShieldTargetPositionSensor(coordinator, entry, cover_entity),
        SolarShieldSunActiveSensor(coordinator, entry, cover_entity),
        SolarShieldStatusSensor(coordinator, entry, cover_entity),
    ])


class SolarShieldBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for SolarShield sensors."""

    def __init__(
        self,
        coordinator: SolarShieldCoordinator,
        entry: ConfigEntry,
        cover_entity: str,
        sensor_key: str,
        name_suffix: str,
        icon: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._cover_entity = cover_entity
        self._sensor_key = sensor_key
        self._attr_name = f"SolarShield {cover_entity} {name_suffix}"
        self._attr_unique_id = f"solarshield_{entry.entry_id}_{sensor_key}"
        self._attr_icon = icon

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info to group sensors under a single device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"SolarShield ({self._cover_entity})",
            "manufacturer": "SolarShield HA",
            "model": "Sun-based cover controller",
            "entry_type": "service",
        }


class SolarShieldTargetPositionSensor(SolarShieldBaseSensor):
    """Sensor: calculated target position for the cover (0-100)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, coordinator, entry, cover_entity):
        """Initialize."""
        super().__init__(
            coordinator, entry, cover_entity,
            sensor_key="target_position",
            name_suffix="Target Position",
            icon="mdi:blinds",
        )

    @property
    def native_value(self) -> int | None:
        """Return the calculated cover position."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("target_position")


class SolarShieldSunActiveSensor(SolarShieldBaseSensor):
    """Sensor: whether the sun is currently hitting the window."""

    def __init__(self, coordinator, entry, cover_entity):
        """Initialize."""
        super().__init__(
            coordinator, entry, cover_entity,
            sensor_key="sun_active",
            name_suffix="Sun Active",
            icon="mdi:weather-sunny",
        )

    @property
    def native_value(self) -> str | None:
        """Return whether the sun is active on the window."""
        if not self.coordinator.data:
            return None
        active = self.coordinator.data.get("sun_active")
        if active is None:
            return None
        return "on" if active else "off"


class SolarShieldStatusSensor(SolarShieldBaseSensor):
    """Sensor: current operational status of the controller."""

    def __init__(self, coordinator, entry, cover_entity):
        """Initialize."""
        super().__init__(
            coordinator, entry, cover_entity,
            sensor_key="status",
            name_suffix="Status",
            icon="mdi:shield-sun",
        )

    @property
    def native_value(self) -> str:
        """Return the current status as a human-readable string."""
        data = self.coordinator.data
        if not data:
            return "unavailable"
        if data.get("error"):
            return f"error: {data['error']}"
        if data.get("override"):
            remaining = data.get("override_remaining_min", 0)
            return f"override ({remaining} min)"
        if data.get("lux_below_threshold"):
            return "lux_low"
        if data.get("room_empty"):
            return "room_empty"
        if data.get("command_sent"):
            return "active"
        if data.get("skipped_hysteresis"):
            return "stable"
        if not data.get("sun_active"):
            return "sun_not_facing"
        return "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional diagnostic attributes."""
        data = self.coordinator.data or {}
        return {
            "sun_elevation": data.get("sun_elevation"),
            "sun_azimuth": data.get("sun_azimuth"),
            "target_position": data.get("target_position"),
            "sun_active": data.get("sun_active"),
            "override_active": self.coordinator.is_overridden,
        }
