"""Tests for SolarShieldCoordinator."""
import sys
import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# Clean module cache to prevent cross-test import side effects
for mod in list(sys.modules.keys()):
    if mod.startswith('custom_components.solarshield') or mod.startswith('homeassistant'):
        del sys.modules[mod]

# Define submodules to mock
mock_modules = [
    'homeassistant.helpers.config_validation',
    'homeassistant.helpers.entity_registry',
    'homeassistant.helpers.entity_platform',
    'homeassistant.components',
    'homeassistant.components.sensor',
]
for mod in mock_modules:
    sys.modules[mod] = MagicMock()

# Setup config_entries mock
config_entries_mock = MagicMock()
sys.modules['homeassistant.config_entries'] = config_entries_mock

# Setup DT Util Mock
dt_mock = MagicMock()
dt_mock.utcnow = MagicMock(return_value=datetime.datetime(2026, 5, 30, 12, 0, 0, tzinfo=datetime.timezone.utc))

util_mock = MagicMock()
util_mock.dt = dt_mock
sys.modules['homeassistant.util'] = util_mock
sys.modules['homeassistant.util.dt'] = dt_mock

# Setup Event Mock
event_mock = MagicMock()
state_change_callback = None

def mock_track_state_change(hass, entity_ids, action):
    global state_change_callback
    state_change_callback = action
    return MagicMock() # returns unsub function

event_mock.async_track_state_change_event = mock_track_state_change
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

# Setup parent homeassistant mock with hierarchy
homeassistant_mock = MagicMock()
homeassistant_mock.config_entries = config_entries_mock
homeassistant_mock.util = util_mock
sys.modules['homeassistant'] = homeassistant_mock
sys.modules['homeassistant.core'] = MagicMock()

# Now import coordinator and consts safely
from custom_components.solarshield.coordinator import SolarShieldCoordinator
from custom_components.solarshield.const import (
    CONF_COVER_ENTITY,
    CONF_WINDOW_AZIMUTH,
    CONF_GLASS_HEIGHT,
    CONF_SILL_HEIGHT,
    CONF_PROTECT_DISTANCE,
    CONF_PROTECT_HEIGHT,
    CONF_LUX_SENSOR,
    CONF_LUX_THRESHOLD,
    CONF_PRESENCE_SENSOR,
    CONF_MAX_POSITION,
    CONF_MIN_POSITION,
    CONF_OVERRIDE_DURATION,
)



@pytest.fixture
def mock_hass():
    """Fixture for mocked HomeAssistant."""
    hass = MagicMock()
    
    # Mock States
    sun_state = MagicMock()
    sun_state.attributes = {"elevation": 25.0, "azimuth": 180.0}
    
    cover_state = MagicMock()
    cover_state.state = "open"
    cover_state.attributes = {"current_position": 100}

    def get_state(entity_id):
        if entity_id == "sun.sun":
            return sun_state
        if entity_id == "cover.living_room":
            return cover_state
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    hass.services.async_call = AsyncMock()
    
    return hass


@pytest.fixture
def base_config():
    """Fixture for base configuration."""
    return {
        CONF_COVER_ENTITY: "cover.living_room",
        CONF_WINDOW_AZIMUTH: 180.0,
        CONF_GLASS_HEIGHT: 150,
        CONF_SILL_HEIGHT: 90,
        CONF_PROTECT_DISTANCE: 120,
        CONF_PROTECT_HEIGHT: 75,
        CONF_MAX_POSITION: 100,
        CONF_MIN_POSITION: 10,
        CONF_OVERRIDE_DURATION: 60,
    }


@pytest.mark.asyncio
async def test_coordinator_init(mock_hass, base_config):
    """Test coordinator initialization and cover state recovery."""
    coordinator = SolarShieldCoordinator(mock_hass, "entry_123", base_config)
    assert coordinator._last_position == 100
    assert coordinator._unsub_tracker is not None


@pytest.mark.asyncio
async def test_evaluate_and_apply_sun_active(mock_hass, base_config):
    """Test cover positioning when the sun is active on the window."""
    coordinator = SolarShieldCoordinator(mock_hass, "entry_123", base_config)
    
    # Run update
    result = await coordinator._async_update_data()
    
    # Verified sun is active and target position was calculated
    assert result["sun_active"] is True
    assert 10 <= result["target_position"] <= 100
    assert result["command_sent"] is True
    
    # Verify async_call was made to set position
    mock_hass.services.async_call.assert_called_once_with(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.living_room", "position": result["target_position"]},
        blocking=False,
    )


@pytest.mark.asyncio
async def test_evaluate_and_apply_sun_inactive(mock_hass, base_config):
    """Test cover opening when the sun is inactive (e.g. azimuth not matching)."""
    # Set sun azimuth to North (0) while window faces South (180)
    sun_state = mock_hass.states.get("sun.sun")
    sun_state.attributes = {"elevation": 25.0, "azimuth": 0.0}
    
    # Set cover last position to 40 so hysteresis doesn't skip
    coordinator = SolarShieldCoordinator(mock_hass, "entry_123", base_config)
    coordinator._last_position = 40
    
    result = await coordinator._async_update_data()
    
    assert result["sun_active"] is False
    assert result["target_position"] == 100 # should be max_position
    assert result["command_sent"] is True
    
    # Verify it opened the cover
    mock_hass.services.async_call.assert_called_once_with(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.living_room", "position": 100},
        blocking=False,
    )


@pytest.mark.asyncio
async def test_evaluate_and_apply_lux_below_threshold(mock_hass, base_config):
    """Test cover opening when lux is below threshold."""
    base_config[CONF_LUX_SENSOR] = "sensor.lux"
    base_config[CONF_LUX_THRESHOLD] = 5000
    
    # Mock lux state to be below threshold (2000)
    lux_state = MagicMock()
    lux_state.state = "2000"
    
    orig_get = mock_hass.states.get
    def get_state(entity_id):
        if entity_id == "sensor.lux":
            return lux_state
        return orig_get(entity_id)
    
    mock_hass.states.get = MagicMock(side_effect=get_state)
    
    coordinator = SolarShieldCoordinator(mock_hass, "entry_123", base_config)
    coordinator._last_position = 40
    
    result = await coordinator._async_update_data()
    
    assert result["lux_below_threshold"] is True
    assert result["lux"] == 2000.0
    assert result["target_position"] == 100
    assert result["command_sent"] is True


@pytest.mark.asyncio
async def test_evaluate_and_apply_presence_empty(mock_hass, base_config):
    """Test presence sensor stops cover control."""
    base_config[CONF_PRESENCE_SENSOR] = "binary_sensor.presence"
    
    presence_state = MagicMock()
    presence_state.state = "off"
    
    orig_get = mock_hass.states.get
    def get_state(entity_id):
        if entity_id == "binary_sensor.presence":
            return presence_state
        return orig_get(entity_id)
        
    mock_hass.states.get = MagicMock(side_effect=get_state)
    
    coordinator = SolarShieldCoordinator(mock_hass, "entry_123", base_config)
    
    result = await coordinator._async_update_data()
    
    assert result.get("room_empty") is True
    assert mock_hass.services.async_call.call_count == 0


@pytest.mark.asyncio
async def test_safe_sun_attributes_none(mock_hass, base_config):
    """Test that missing or None sun attributes are handled gracefully."""
    sun_state = mock_hass.states.get("sun.sun")
    sun_state.attributes = {"elevation": None, "azimuth": None}
    
    coordinator = SolarShieldCoordinator(mock_hass, "entry_123", base_config)
    result = await coordinator._async_update_data()
    
    assert result == {"error": "invalid_sun_attributes"}


@pytest.mark.asyncio
async def test_manual_override_detection(mock_hass, base_config):
    """Test that manual cover adjustments trigger override mode."""
    global state_change_callback
    coordinator = SolarShieldCoordinator(mock_hass, "entry_123", base_config)
    
    # We expected position 80, but state change reports 50
    coordinator._last_position = 80
    
    # Simulate a state change event
    event = MagicMock()
    old_state = MagicMock()
    old_state.state = "open"
    old_state.attributes = {"current_position": 80}
    
    new_state = MagicMock()
    new_state.state = "open"
    new_state.attributes = {"current_position": 50}
    
    event.data = {"old_state": old_state, "new_state": new_state}
    
    # Trigger callback
    assert state_change_callback is not None
    await state_change_callback(event)
    
    # Override should be active now
    assert coordinator.is_overridden is True
    
    # Check evaluation returns override
    result = await coordinator._async_update_data()
    assert result["override"] is True
    
    # Clear override
    coordinator.clear_manual_override()
    assert coordinator.is_overridden is False
