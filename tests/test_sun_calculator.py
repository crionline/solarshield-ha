"""Tests for sun_calculator module."""
import math
import pytest

from custom_components.solarshield.sun_calculator import (
    calculate_cover_position,
    calculate_required_shade_height,
    is_sun_facing_window,
    shade_height_to_cover_position,
)


def test_sun_facing_window_south():
    """Sun at 180° azimuth, window facing south (180°), width 60°."""
    assert is_sun_facing_window(180, 180, 60) is True
    assert is_sun_facing_window(210, 180, 60) is True
    assert is_sun_facing_window(211, 180, 60) is False
    assert is_sun_facing_window(150, 180, 60) is True
    assert is_sun_facing_window(149, 180, 60) is False


def test_sun_not_facing_window_north():
    """Sun at 0° (north), window facing south."""
    assert is_sun_facing_window(0, 180, 60) is False
    assert is_sun_facing_window(90, 180, 60) is False


def test_shade_height_basic():
    """Standard case: desk at 75cm, 120cm from window, sun at 30°."""
    h = calculate_required_shade_height(30, 120, 75, 90)
    expected = 120 * math.tan(math.radians(30)) + 75
    assert abs(h - expected) < 0.1


def test_shade_height_sun_below_horizon():
    """Sun below horizon returns sill height."""
    h = calculate_required_shade_height(-5, 120, 75, 90)
    assert h == 90


def test_cover_position_sun_not_active():
    """Sun not facing window: position should be max."""
    position, active = calculate_cover_position(
        sun_elevation_deg=45,
        sun_azimuth_deg=0,
        window_azimuth_deg=180,
        window_angular_width_deg=60,
        glass_height_cm=150,
        sill_height_cm=90,
        protect_distance_cm=120,
        protect_height_cm=75,
    )
    assert active is False
    assert position == 100


def test_cover_position_sun_active_high_elevation():
    """Sun high (70°) facing south window: cover should be quite open."""
    position, active = calculate_cover_position(
        sun_elevation_deg=70,
        sun_azimuth_deg=180,
        window_azimuth_deg=180,
        window_angular_width_deg=60,
        glass_height_cm=150,
        sill_height_cm=90,
        protect_distance_cm=120,
        protect_height_cm=75,
    )
    assert active is True
    assert 10 <= position <= 100


def test_cover_position_clamped_to_min():
    """Very low sun elevation with close protect point should clamp to min."""
    position, active = calculate_cover_position(
        sun_elevation_deg=5,
        sun_azimuth_deg=180,
        window_azimuth_deg=180,
        window_angular_width_deg=60,
        glass_height_cm=150,
        sill_height_cm=90,
        protect_distance_cm=300,
        protect_height_cm=0,
        min_position=10,
    )
    assert active is True
    assert position >= 10
