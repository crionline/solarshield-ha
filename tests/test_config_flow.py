"""Tests for SolarShieldConfigFlow and SolarShieldOptionsFlow."""
import sys
from unittest.mock import MagicMock
import pytest

# Clean module cache to prevent cross-test import side effects
for mod in list(sys.modules.keys()):
    if mod.startswith('custom_components.solarshield') or mod.startswith('homeassistant'):
        del sys.modules[mod]

# Define submodules to mock
mock_modules = [
    'homeassistant.helpers',
    'homeassistant.helpers.config_validation',
    'homeassistant.helpers.entity_registry',
    'homeassistant.helpers.event',
    'homeassistant.helpers.entity_platform',
    'homeassistant.helpers.update_coordinator',
    'homeassistant.components',
    'homeassistant.components.sensor',
]
for mod in mock_modules:
    sys.modules[mod] = MagicMock()

# Setup DT Util Mock
dt_mock = MagicMock()
import datetime
dt_mock.utcnow = MagicMock(return_value=datetime.datetime(2026, 5, 30, 12, 0, 0, tzinfo=datetime.timezone.utc))

util_mock = MagicMock()
util_mock.dt = dt_mock
sys.modules['homeassistant.util'] = util_mock
sys.modules['homeassistant.util.dt'] = dt_mock

# Setup Event Mock
event_mock = MagicMock()
event_mock.async_track_state_change_event = MagicMock()
sys.modules['homeassistant.helpers.event'] = event_mock

# Setup Update Coordinator Mock
class MockDataUpdateCoordinator:
    def __init__(self, hass, logger, *, name, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}

    async def async_refresh(self):
        self.data = await self._async_update_data()

update_coordinator_mock = MagicMock()
update_coordinator_mock.DataUpdateCoordinator = MockDataUpdateCoordinator
sys.modules['homeassistant.helpers.update_coordinator'] = update_coordinator_mock

# Setup config_entries mock with base classes we can subclass
class MockConfigFlow:
    @classmethod
    def __init_subclass__(cls, **kwargs):
        pass

    def __init__(self):
        self.cur_step = None
        self.unique_id = None

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id
        return unique_id

    def _abort_if_unique_id_configured(self):
        pass

    def async_show_form(self, step_id, data_schema, errors=None, description_placeholders=None):
        self.cur_step = step_id
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(self, title, data):
        return {
            "type": "create_entry",
            "title": title,
            "data": data,
        }

class MockOptionsFlow:
    def __init__(self):
        self.config_entry = MagicMock()
        self.config_entry.data = {}
        self.config_entry.options = {}

    def async_show_form(self, step_id, data_schema, errors=None):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(self, title, data):
        return {
            "type": "create_entry",
            "title": title,
            "data": data,
        }

config_entries_mock = MagicMock()
config_entries_mock.ConfigFlow = MockConfigFlow
config_entries_mock.OptionsFlow = MockOptionsFlow
sys.modules['homeassistant.config_entries'] = config_entries_mock

# Setup config_validation mock
cv_mock = MagicMock()
cv_mock.entity_id = lambda v: v
sys.modules['homeassistant.helpers.config_validation'] = cv_mock

# Setup parent homeassistant mock with hierarchy
homeassistant_mock = MagicMock()
homeassistant_mock.config_entries = config_entries_mock
homeassistant_mock.util = util_mock

helpers_mock = MagicMock()
helpers_mock.config_validation = cv_mock
helpers_mock.entity_registry = sys.modules['homeassistant.helpers.entity_registry']
helpers_mock.event = event_mock
helpers_mock.update_coordinator = update_coordinator_mock
homeassistant_mock.helpers = helpers_mock

sys.modules['homeassistant.helpers'] = helpers_mock
sys.modules['homeassistant'] = homeassistant_mock
sys.modules['homeassistant.core'] = MagicMock()

# Now import the flows safely
from custom_components.solarshield.config_flow import SolarShieldConfigFlow, SolarShieldOptionsFlow
from custom_components.solarshield.const import (
    CONF_WINDOW_AZIMUTH,
    CONF_WINDOW_ANGULAR_WIDTH,
    CONF_GLASS_HEIGHT,
    CONF_SILL_HEIGHT,
    CONF_PROTECT_DISTANCE,
    CONF_PROTECT_HEIGHT,
    CONF_COVER_ENTITY,
    CONF_COVER_TYPE,
    CONF_MIN_POSITION,
    CONF_MAX_POSITION,
    CONF_HYSTERESIS,
    CONF_UPDATE_INTERVAL,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_PRESENCE_SENSOR,
    CONF_OVERRIDE_DURATION,
    COVER_TYPE_BLIND,
)


@pytest.mark.asyncio
async def test_config_flow_steps():
    """Test the complete setup configuration flow step-by-step."""
    flow = SolarShieldConfigFlow()

    # Step 1: User step (Geometry) - Show form
    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    # Step 1: Submit valid geometry
    geometry_data = {
        CONF_WINDOW_AZIMUTH: 180,
        CONF_WINDOW_ANGULAR_WIDTH: 60,
        CONF_GLASS_HEIGHT: 150,
        CONF_SILL_HEIGHT: 90,
        CONF_PROTECT_DISTANCE: 120,
        CONF_PROTECT_HEIGHT: 75,
    }
    result = await flow.async_step_user(geometry_data)
    assert flow._geometry == geometry_data

    # Step 2: Cover step - Show form
    assert result["type"] == "form"
    assert result["step_id"] == "cover"

    # Step 2: Submit valid cover config
    cover_data = {
        CONF_COVER_ENTITY: "cover.living_room",
        CONF_COVER_TYPE: COVER_TYPE_BLIND,
        CONF_MIN_POSITION: 10,
        CONF_MAX_POSITION: 100,
        CONF_HYSTERESIS: 5,
        CONF_UPDATE_INTERVAL: 5,
    }
    result = await flow.async_step_cover(cover_data)
    assert flow._cover == cover_data

    # Step 3: Optional step - Show form
    assert result["type"] == "form"
    assert result["step_id"] == "optional"

    # Step 3: Submit valid optional config & complete flow
    optional_data = {
        CONF_LUX_SENSOR: "sensor.lux",
        CONF_LUX_THRESHOLD: 4000,
        CONF_PRESENCE_SENSOR: "binary_sensor.occupancy",
        CONF_OVERRIDE_DURATION: 30,
    }
    result = await flow.async_step_optional(optional_data)
    
    assert result["type"] == "create_entry"
    assert result["title"] == "SolarShield (cover.living_room)"
    
    # Check that all data is merged correctly
    expected_data = {**geometry_data, **cover_data, **optional_data}
    assert result["data"] == expected_data


@pytest.mark.asyncio
async def test_options_flow():
    """Test the options flow for changing configurations."""
    flow = SolarShieldOptionsFlow()
    
    # Set up config entry data
    flow.config_entry.data = {
        CONF_WINDOW_AZIMUTH: 180,
        CONF_COVER_ENTITY: "cover.living_room",
    }
    flow.config_entry.options = {
        CONF_LUX_THRESHOLD: 5000,
        CONF_HYSTERESIS: 5,
    }

    # Step 1: Init options flow - Show form
    result = await flow.async_step_init(None)
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    # Step 1: Submit new options
    updated_options = {
        CONF_LUX_THRESHOLD: 8000,
        CONF_HYSTERESIS: 10,
        CONF_UPDATE_INTERVAL: 10,
        CONF_OVERRIDE_DURATION: 120,
        CONF_MIN_POSITION: 20,
        CONF_MAX_POSITION: 90,
    }
    result = await flow.async_step_init(updated_options)
    
    assert result["type"] == "create_entry"
    assert result["data"] == updated_options
