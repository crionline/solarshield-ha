"""DataUpdateCoordinator for SolarShield HA."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_AZIMUTH,
    ATTR_ELEVATION,
    CONF_COVER_ENTITY,
    CONF_COVER_TYPE,
    CONF_GLASS_HEIGHT,
    CONF_HYSTERESIS,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_MAX_POSITION,
    CONF_MIN_POSITION,
    CONF_OVERRIDE_DURATION,
    CONF_PRESENCE_SENSOR,
    CONF_PROTECT_DISTANCE,
    CONF_PROTECT_HEIGHT,
    CONF_SILL_HEIGHT,
    CONF_UPDATE_INTERVAL,
    CONF_WINDOW_ANGULAR_WIDTH,
    CONF_WINDOW_AZIMUTH,
    DEFAULT_HYSTERESIS,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DEFAULT_OVERRIDE_DURATION,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SUN_ENTITY,
)
from .sun_calculator import calculate_cover_position

_LOGGER = logging.getLogger(__name__)


class SolarShieldCoordinator(DataUpdateCoordinator):
    """Manages sun tracking and cover control for a single window."""

    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict) -> None:
        """Initialize the coordinator."""
        self._config = config
        self._entry_id = entry_id
        self._override_until: datetime | None = None
        self._last_position: int | None = None

        update_interval = timedelta(
            minutes=config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and apply cover position."""
        return await self._evaluate_and_apply()

    async def _evaluate_and_apply(self) -> dict[str, Any]:
        """Evaluate sun position and apply cover command if needed."""
        config = self._config
        now = dt_util.utcnow()

        # Check manual override
        if self._override_until and now < self._override_until:
            remaining = (self._override_until - now).seconds // 60
            _LOGGER.debug("SolarShield: manual override active, %d min remaining", remaining)
            return {"override": True, "override_remaining_min": remaining}

        # Get sun state
        sun_state = self.hass.states.get(SUN_ENTITY)
        if not sun_state:
            _LOGGER.warning("SolarShield: sun.sun entity not found")
            return {"error": "sun_not_found"}

        elevation = float(sun_state.attributes.get(ATTR_ELEVATION, 0))
        azimuth = float(sun_state.attributes.get(ATTR_AZIMUTH, 0))

        # Check lux threshold
        lux_sensor = config.get(CONF_LUX_SENSOR)
        if lux_sensor:
            lux_state = self.hass.states.get(lux_sensor)
            if lux_state:
                try:
                    lux = float(lux_state.state)
                    threshold = config.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD)
                    if lux < threshold:
                        _LOGGER.debug(
                            "SolarShield: lux %.0f below threshold %d, releasing cover",
                            lux, threshold
                        )
                        return {"lux_below_threshold": True, "lux": lux}
                except (ValueError, TypeError):
                    pass

        # Check presence
        presence_sensor = config.get(CONF_PRESENCE_SENSOR)
        if presence_sensor:
            presence_state = self.hass.states.get(presence_sensor)
            if presence_state and presence_state.state not in ("on", "home", "detected"):
                _LOGGER.debug("SolarShield: room not occupied, skipping")
                return {"room_empty": True}

        # Calculate cover position
        position, sun_active = calculate_cover_position(
            sun_elevation_deg=elevation,
            sun_azimuth_deg=azimuth,
            window_azimuth_deg=config[CONF_WINDOW_AZIMUTH],
            window_angular_width_deg=config.get(CONF_WINDOW_ANGULAR_WIDTH, 60),
            glass_height_cm=config[CONF_GLASS_HEIGHT],
            sill_height_cm=config[CONF_SILL_HEIGHT],
            protect_distance_cm=config[CONF_PROTECT_DISTANCE],
            protect_height_cm=config[CONF_PROTECT_HEIGHT],
            min_position=config.get(CONF_MIN_POSITION, DEFAULT_MIN_POSITION),
            max_position=config.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION),
        )

        result = {
            "sun_elevation": elevation,
            "sun_azimuth": azimuth,
            "sun_active": sun_active,
            "target_position": position,
        }

        if not sun_active:
            return result

        # Apply hysteresis
        hysteresis = config.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        if (
            self._last_position is not None
            and abs(position - self._last_position) < hysteresis
        ):
            _LOGGER.debug(
                "SolarShield: position change %d -> %d below hysteresis %d, skipping",
                self._last_position, position, hysteresis
            )
            result["skipped_hysteresis"] = True
            return result

        # Send cover command
        cover_entity = config[CONF_COVER_ENTITY]
        _LOGGER.info(
            "SolarShield: setting %s to position %d (elevation=%.1f, azimuth=%.1f)",
            cover_entity, position, elevation, azimuth
        )

        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": cover_entity, "position": position},
            blocking=False,
        )
        self._last_position = position
        result["command_sent"] = True

        return result

    def set_manual_override(self) -> None:
        """Activate manual override."""
        duration = self._config.get(CONF_OVERRIDE_DURATION, DEFAULT_OVERRIDE_DURATION)
        self._override_until = dt_util.utcnow() + timedelta(minutes=duration)
        _LOGGER.info(
            "SolarShield: manual override activated for %d minutes", duration
        )

    def clear_manual_override(self) -> None:
        """Clear manual override."""
        self._override_until = None
        _LOGGER.info("SolarShield: manual override cleared")

    @property
    def is_overridden(self) -> bool:
        """Return True if manual override is active."""
        if not self._override_until:
            return False
        return dt_util.utcnow() < self._override_until

    def update_config(self, new_config: dict) -> None:
        """Update coordinator config after options flow change."""
        self._config = {**self._config, **new_config}
