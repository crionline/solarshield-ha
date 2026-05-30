"""DataUpdateCoordinator for SolarShield HA."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
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
    COVER_TYPE_BLIND,
    COVER_TYPE_VENETIAN,
    DEFAULT_HYSTERESIS,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DEFAULT_OVERRIDE_DURATION,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SUN_ENTITY,
)
from .sun_calculator import calculate_cover_position, calculate_venetian_tilt

_LOGGER = logging.getLogger(__name__)


class SolarShieldCoordinator(DataUpdateCoordinator):
    """Manages sun tracking and cover control for a single window."""

    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict) -> None:
        """Initialize the coordinator."""
        self._config = config
        self._entry_id = entry_id
        self._override_until: datetime | None = None
        self._last_position: int | None = None
        self._unsub_tracker = None

        # Try to initialize self._last_position from the current state of the cover
        cover_entity = config.get(CONF_COVER_ENTITY)
        if cover_entity:
            cover_state = hass.states.get(cover_entity)
            if cover_state:
                try:
                    self._last_position = int(cover_state.attributes.get("current_position"))
                except (TypeError, ValueError):
                    pass

            # Track cover entity state changes to detect manual override
            self._unsub_tracker = async_track_state_change_event(
                hass, [cover_entity], self._async_handle_cover_state_change
            )

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
            remaining = int((self._override_until - now).total_seconds() // 60)
            _LOGGER.debug("SolarShield: manual override active, %d min remaining", remaining)
            return {"override": True, "override_remaining_min": remaining}

        # Get sun state
        sun_state = self.hass.states.get(SUN_ENTITY)
        if not sun_state:
            _LOGGER.warning("SolarShield: sun.sun entity not found")
            return {"error": "sun_not_found"}

        try:
            elevation = sun_state.attributes.get(ATTR_ELEVATION)
            azimuth = sun_state.attributes.get(ATTR_AZIMUTH)
            if elevation is None or azimuth is None:
                raise ValueError("Sun elevation or azimuth is None")
            elevation = float(elevation)
            azimuth = float(azimuth)
        except (ValueError, TypeError) as err:
            _LOGGER.error("SolarShield: invalid sun attributes: %s", err)
            return {"error": "invalid_sun_attributes"}

        # Check lux threshold
        lux_sensor = config.get(CONF_LUX_SENSOR)
        lux_low = False
        lux_val = None
        if lux_sensor:
            lux_state = self.hass.states.get(lux_sensor)
            if lux_state:
                try:
                    lux_val = float(lux_state.state)
                    threshold = config.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD)
                    if lux_val < threshold:
                        _LOGGER.debug(
                            "SolarShield: lux %.0f below threshold %d, releasing cover",
                            lux_val, threshold
                        )
                        lux_low = True
                except (ValueError, TypeError) as err:
                    _LOGGER.warning("SolarShield: invalid lux sensor state: %s", err)

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

        # If sun is not active on the window, or lux is below threshold,
        # the cover should be set to max_position (released/opened).
        target_position = position
        if not sun_active or lux_low:
            target_position = config.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION)

        result = {
            "sun_elevation": elevation,
            "sun_azimuth": azimuth,
            "sun_active": sun_active,
            "target_position": target_position,
        }

        if lux_low:
            result["lux_below_threshold"] = True
            if lux_val is not None:
                result["lux"] = lux_val

        # Apply hysteresis
        hysteresis = config.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        if (
            self._last_position is not None
            and abs(target_position - self._last_position) < hysteresis
        ):
            _LOGGER.debug(
                "SolarShield: position change %d -> %d below hysteresis %d, skipping",
                self._last_position, target_position, hysteresis
            )
            result["skipped_hysteresis"] = True
            return result

        # Send cover command
        cover_entity = config[CONF_COVER_ENTITY]
        _LOGGER.info(
            "SolarShield: setting %s to position %d (elevation=%.1f, azimuth=%.1f, sun_active=%s, lux_low=%s)",
            cover_entity, target_position, elevation, azimuth, sun_active, lux_low
        )

        await self.hass.services.async_call(
            "cover",
            "set_cover_position",
            {"entity_id": cover_entity, "position": target_position},
            blocking=False,
        )
        self._last_position = target_position
        result["command_sent"] = True

        # For venetian blinds, also send optimal tilt
        cover_type = config.get(CONF_COVER_TYPE, COVER_TYPE_BLIND)
        if cover_type == COVER_TYPE_VENETIAN and sun_active and not lux_low:
            tilt = calculate_venetian_tilt(elevation)
            await self.hass.services.async_call(
                "cover",
                "set_cover_tilt_position",
                {"entity_id": cover_entity, "tilt_position": tilt},
                blocking=False,
            )
            result["tilt_position"] = tilt
            _LOGGER.info(
                "SolarShield: setting tilt of %s to %d%% (elevation=%.1f)",
                cover_entity, tilt, elevation
            )

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

    async def _async_handle_cover_state_change(self, event) -> None:
        """Handle state change of the tracked cover entity."""
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state or not old_state:
            return

        # If the cover is currently moving, wait until it stops to evaluate
        if new_state.state in ("opening", "closing"):
            return

        # We are interested in the position attribute
        new_position = new_state.attributes.get("current_position")
        old_position = old_state.attributes.get("current_position")

        if new_position is None:
            return

        # If the position and state haven't changed, ignore
        if old_position is not None and new_position == old_position:
            if new_state.state == old_state.state:
                return

        # If we haven't sent any command yet, initialize and don't trigger override
        if self._last_position is None:
            self._last_position = int(new_position)
            return

        # Check if the final position matches our last commanded position (2% tolerance)
        if abs(int(new_position) - self._last_position) <= 2:
            return

        # The position does not match our target, meaning it was moved manually
        _LOGGER.info(
            "SolarShield: manual cover movement detected for %s (final position %s, expected %s). Activating manual override.",
            self._config[CONF_COVER_ENTITY], new_position, self._last_position
        )
        self.set_manual_override()
        await self.async_refresh()

    async def async_close(self) -> None:
        """Close resources and remove listeners."""
        if self._unsub_tracker:
            self._unsub_tracker()
            self._unsub_tracker = None
