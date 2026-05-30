# SolarShield HA

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

**Home Assistant custom integration** to automatically control covers/blinds based on sun position, preventing direct sunlight from entering rooms.

## Features

- Calculates the optimal cover position based on sun elevation and azimuth
- Geometry-based algorithm: accounts for window orientation, height, and the point to protect
- Supports position-only covers and tilt covers (venetian blinds)
- Manual override with configurable suspend duration
- Lux threshold to avoid unnecessary movements on cloudy days
- Hysteresis to prevent micro-adjustments
- Rate limiting (configurable interval)
- Presence sensor support

## Requirements

- Home Assistant 2024.1+
- A cover entity that supports `set_cover_position` (0-100)
- Sun integration enabled (default in HA)

## Installation via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=crionline&repository=solarshield-ha&category=integration)

1. Add this repository as a custom HACS repository (Integration type)
2. Install **SolarShield HA**
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration** and search for **SolarShield**

## Manual Installation

1. Copy the `custom_components/solarshield` folder into your HA `custom_components` directory
2. Restart Home Assistant
3. Add the integration from the UI

## Configuration

All configuration is done via the UI config flow. You will be asked for:

### Window & Room Geometry

| Parameter | Description | Example |
|---|---|---|
| Window azimuth | Direction the window faces (degrees from North) | 180 = South |
| Window angular width | Angular width of the window sector | 60° |
| Window glass height | Height of the glass pane (cm) | 150 |
| Sill height | Height of the bottom of the glass from floor (cm) | 90 |
| Protected point distance | Horizontal distance from window to point to protect (cm) | 120 |
| Protected point height | Height of the point to protect from floor (cm) | 75 |

### Cover Settings

| Parameter | Description |
|---|---|
| Cover entity | The cover entity to control |
| Cover type | `blind` (position only) or `venetian` (position + tilt) |
| Min position | Minimum allowed position (default: 10) |
| Max position | Maximum allowed position (default: 100) |
| Position hysteresis | Minimum change before sending a command (default: 5) |
| Tilt hysteresis | Minimum tilt change before sending a command (default: 5) |
| Update interval | How often to recalculate (minutes, default: 5) |

### Optional

| Parameter | Description |
|---|---|
| Lux sensor | External lux sensor entity |
| Lux threshold | Minimum lux to activate (default: 5000) |
| Presence sensor | Room presence sensor entity |
| Manual override duration | Minutes to suspend automation after manual move (default: 60) |

## Algorithm

The core formula to determine the required shade height on the window plane:

```
h = d × tan(α) + q
```

Where:
- `h` = minimum shadow height on the window plane
- `d` = horizontal distance from window to the point to protect (cm)
- `α` = sun elevation angle
- `q` = height of the protected point from the floor (cm)

The cover position is then derived from `h` relative to the glass height and sill height.

## Venetian Blind Tilt Algorithm

For `venetian` covers, an optimal slat tilt angle is calculated to block direct sunlight
while allowing diffuse light through:

```
tilt = (90 - α) / 90 × 100
```

Where:
- `tilt` = tilt position sent to HA (0 = slats horizontal, 100 = slats vertical)
- `α` = sun elevation angle

This means slats are angled perpendicular to the incoming sun rays:
- High sun (α → 90°): slats nearly horizontal → `tilt → 0`
- Low sun (α → 0°): slats nearly vertical → `tilt → 100`

Tilt is only applied when the sun is active on the window and lux is above threshold.

## License

MIT License - see [LICENSE](LICENSE)
