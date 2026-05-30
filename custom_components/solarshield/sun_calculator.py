"""Sun geometry calculations for SolarShield HA."""
from __future__ import annotations

import math


def is_sun_facing_window(
    sun_azimuth: float,
    window_azimuth: float,
    window_angular_width: float,
) -> bool:
    """Return True if the sun is within the window's angular sector."""
    half_width = window_angular_width / 2.0
    diff = (sun_azimuth - window_azimuth + 180) % 360 - 180
    return abs(diff) <= half_width


def calculate_required_shade_height(
    sun_elevation_deg: float,
    protect_distance_cm: float,
    protect_height_cm: float,
    sill_height_cm: float,
) -> float:
    """
    Calculate the required shade height on the window plane (in cm from floor).

    Formula: h = d * tan(alpha) + q
    Where:
      h = height on window plane that must be in shadow
      d = horizontal distance from window to point to protect
      alpha = sun elevation angle
      q = height of the protected point from the floor

    Returns the height from the floor that must be shaded.
    """
    if sun_elevation_deg <= 0:
        return sill_height_cm  # Sun below horizon, no shade needed

    alpha_rad = math.radians(sun_elevation_deg)
    h = protect_distance_cm * math.tan(alpha_rad) + protect_height_cm
    return h


def shade_height_to_cover_position(
    required_shade_height_cm: float,
    sill_height_cm: float,
    glass_height_cm: float,
    min_position: int = 10,
    max_position: int = 100,
) -> int:
    """
    Convert required shade height to cover position (0=closed, 100=open).

    The cover lowers from the top. Position 100 = fully open (no cover).
    Position 0 = fully closed.

    We calculate how much of the glass must be covered (from the top),
    then map that to the 0-100 scale.
    """
    top_of_glass = sill_height_cm + glass_height_cm

    # If the required shade height is above the top of the glass, no cover needed
    if required_shade_height_cm >= top_of_glass:
        return max_position

    # If required shade is below the sill, full cover needed
    if required_shade_height_cm <= sill_height_cm:
        return min_position

    # How much of the glass (from top) needs to be covered
    uncovered_height = required_shade_height_cm - sill_height_cm
    open_fraction = uncovered_height / glass_height_cm  # 0.0 to 1.0

    # Map open_fraction to position range
    position = min_position + open_fraction * (max_position - min_position)
    position = max(min_position, min(max_position, round(position)))
    return int(position)


def calculate_cover_position(
    sun_elevation_deg: float,
    sun_azimuth_deg: float,
    window_azimuth_deg: float,
    window_angular_width_deg: float,
    glass_height_cm: float,
    sill_height_cm: float,
    protect_distance_cm: float,
    protect_height_cm: float,
    min_position: int = 10,
    max_position: int = 100,
) -> tuple[int, bool]:
    """
    Main entry point: calculate the optimal cover position.

    Returns:
      (position, sun_active) where:
        position: int 0-100
        sun_active: bool, True if sun is currently facing the window
    """
    sun_active = is_sun_facing_window(
        sun_azimuth_deg, window_azimuth_deg, window_angular_width_deg
    )

    if not sun_active or sun_elevation_deg <= 0:
        return max_position, False

    shade_h = calculate_required_shade_height(
        sun_elevation_deg, protect_distance_cm, protect_height_cm, sill_height_cm
    )

    position = shade_height_to_cover_position(
        shade_h, sill_height_cm, glass_height_cm, min_position, max_position
    )

    return position, True


def calculate_venetian_tilt(
    sun_elevation_deg: float,
    min_tilt: int = 0,
    max_tilt: int = 100,
) -> int:
    """
    Calculate the optimal tilt position for venetian (slatted) blinds.

    The slat angle is chosen so the slats are perpendicular to the sun rays,
    providing maximum shading while allowing diffuse light through.

    Convention (standard HA):
      tilt_position = 0   → slats horizontal  (blocks overhead / high sun)
      tilt_position = 100 → slats vertical     (blocks low / horizon sun)

    Formula: tilt = (90 - sun_elevation) / 90 * 100

    Args:
        sun_elevation_deg: Current sun elevation in degrees (0 = horizon, 90 = zenith)
        min_tilt: Minimum allowed tilt position (default 0)
        max_tilt: Maximum allowed tilt position (default 100)

    Returns:
        Tilt position as integer 0-100.
    """
    if sun_elevation_deg <= 0:
        return max_tilt  # Sun at or below horizon → maximum tilt (vertical slats)

    if sun_elevation_deg >= 90:
        return min_tilt  # Sun directly overhead → slats horizontal

    raw = (90.0 - sun_elevation_deg) / 90.0 * 100.0
    return int(max(min_tilt, min(max_tilt, round(raw))))

