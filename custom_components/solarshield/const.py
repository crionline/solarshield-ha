"""Constants for SolarShield HA."""

DOMAIN = "solarshield"
PLATFORMS = ["sensor"]

# Config keys - Window geometry
CONF_WINDOW_AZIMUTH = "window_azimuth"
CONF_WINDOW_ANGULAR_WIDTH = "window_angular_width"
CONF_GLASS_HEIGHT = "glass_height"
CONF_SILL_HEIGHT = "sill_height"

# Config keys - Protected point
CONF_PROTECT_DISTANCE = "protect_distance"
CONF_PROTECT_HEIGHT = "protect_height"

# Config keys - Cover
CONF_COVER_ENTITY = "cover_entity"
CONF_COVER_TYPE = "cover_type"
CONF_MIN_POSITION = "min_position"
CONF_MAX_POSITION = "max_position"
CONF_HYSTERESIS = "hysteresis"
CONF_UPDATE_INTERVAL = "update_interval"

# Config keys - Optional
CONF_LUX_SENSOR = "lux_sensor"
CONF_LUX_THRESHOLD = "lux_threshold"
CONF_PRESENCE_SENSOR = "presence_sensor"
CONF_OVERRIDE_DURATION = "override_duration"

# Cover types
COVER_TYPE_BLIND = "blind"
COVER_TYPE_VENETIAN = "venetian"

# Defaults
DEFAULT_ANGULAR_WIDTH = 60
DEFAULT_MIN_POSITION = 10
DEFAULT_MAX_POSITION = 100
DEFAULT_HYSTERESIS = 5
DEFAULT_UPDATE_INTERVAL = 5
DEFAULT_LUX_THRESHOLD = 5000
DEFAULT_OVERRIDE_DURATION = 60

# Sun entity
SUN_ENTITY = "sun.sun"
ATTR_ELEVATION = "elevation"
ATTR_AZIMUTH = "azimuth"
