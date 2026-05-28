"""Config flow for SolarShield HA."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
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
    DEFAULT_ANGULAR_WIDTH,
    DEFAULT_HYSTERESIS,
    DEFAULT_LUX_THRESHOLD,
    DEFAULT_MAX_POSITION,
    DEFAULT_MIN_POSITION,
    DEFAULT_OVERRIDE_DURATION,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


class SolarShieldConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SolarShield HA."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Step 1: Window geometry."""
        errors = {}
        if user_input is not None:
            self._geometry = user_input
            return await self.async_step_cover(None)

        schema = vol.Schema({
            vol.Required(CONF_WINDOW_AZIMUTH, description={"suggested_value": 180}): vol.All(
                vol.Coerce(float), vol.Range(min=0, max=359)
            ),
            vol.Required(CONF_WINDOW_ANGULAR_WIDTH, default=DEFAULT_ANGULAR_WIDTH): vol.All(
                vol.Coerce(float), vol.Range(min=10, max=180)
            ),
            vol.Required(CONF_GLASS_HEIGHT): vol.All(
                vol.Coerce(int), vol.Range(min=20, max=400)
            ),
            vol.Required(CONF_SILL_HEIGHT): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=300)
            ),
            vol.Required(CONF_PROTECT_DISTANCE): vol.All(
                vol.Coerce(int), vol.Range(min=10, max=1000)
            ),
            vol.Required(CONF_PROTECT_HEIGHT, default=75): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=300)
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={},
        )

    async def async_step_cover(self, user_input=None):
        """Step 2: Cover entity and settings."""
        errors = {}
        if user_input is not None:
            self._cover = user_input
            return await self.async_step_optional(None)

        schema = vol.Schema({
            vol.Required(CONF_COVER_ENTITY): cv.entity_id,
            vol.Required(CONF_COVER_TYPE, default=COVER_TYPE_BLIND): vol.In(
                [COVER_TYPE_BLIND, COVER_TYPE_VENETIAN]
            ),
            vol.Optional(CONF_MIN_POSITION, default=DEFAULT_MIN_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=50)
            ),
            vol.Optional(CONF_MAX_POSITION, default=DEFAULT_MAX_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=50, max=100)
            ),
            vol.Optional(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=20)
            ),
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
        })

        return self.async_show_form(
            step_id="cover",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_optional(self, user_input=None):
        """Step 3: Optional sensors."""
        if user_input is not None:
            data = {**self._geometry, **self._cover, **user_input}
            cover_id = self._cover[CONF_COVER_ENTITY]
            await self.async_set_unique_id(f"solarshield_{cover_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"SolarShield ({cover_id})",
                data=data,
            )

        schema = vol.Schema({
            vol.Optional(CONF_LUX_SENSOR): cv.entity_id,
            vol.Optional(CONF_LUX_THRESHOLD, default=DEFAULT_LUX_THRESHOLD): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100000)
            ),
            vol.Optional(CONF_PRESENCE_SENSOR): cv.entity_id,
            vol.Optional(CONF_OVERRIDE_DURATION, default=DEFAULT_OVERRIDE_DURATION): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=480)
            ),
        })

        return self.async_show_form(
            step_id="optional",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return options flow."""
        return SolarShieldOptionsFlow(config_entry)


class SolarShieldOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for SolarShield HA."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data
        schema = vol.Schema({
            vol.Optional(CONF_LUX_THRESHOLD, default=data.get(CONF_LUX_THRESHOLD, DEFAULT_LUX_THRESHOLD)): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100000)
            ),
            vol.Optional(CONF_HYSTERESIS, default=data.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=20)
            ),
            vol.Optional(CONF_UPDATE_INTERVAL, default=data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=60)
            ),
            vol.Optional(CONF_OVERRIDE_DURATION, default=data.get(CONF_OVERRIDE_DURATION, DEFAULT_OVERRIDE_DURATION)): vol.All(
                vol.Coerce(int), vol.Range(min=5, max=480)
            ),
            vol.Optional(CONF_MIN_POSITION, default=data.get(CONF_MIN_POSITION, DEFAULT_MIN_POSITION)): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=50)
            ),
            vol.Optional(CONF_MAX_POSITION, default=data.get(CONF_MAX_POSITION, DEFAULT_MAX_POSITION)): vol.All(
                vol.Coerce(int), vol.Range(min=50, max=100)
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
