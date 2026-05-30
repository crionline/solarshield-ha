"""Tests for sun_calculator module."""
import math
import pytest

from custom_components.solarshield.sun_calculator import (
    calculate_cover_position,
    calculate_required_shade_height,
    calculate_venetian_tilt,
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


# ── Venetian tilt tests ────────────────────────────────────────────────────

def test_venetian_tilt_sun_below_horizon():
    """Sun at or below horizon → maximum tilt (vertical slats)."""
    assert calculate_venetian_tilt(0) == 100
    assert calculate_venetian_tilt(-10) == 100


def test_venetian_tilt_sun_at_zenith():
    """Sun directly overhead (90°) → minimum tilt (horizontal slats)."""
    assert calculate_venetian_tilt(90) == 0


def test_venetian_tilt_45_degrees():
    """Sun at 45° → tilt should be 50%."""
    assert calculate_venetian_tilt(45) == 50


def test_venetian_tilt_30_degrees():
    """Sun at 30° → tilt should be ~67%."""
    result = calculate_venetian_tilt(30)
    assert result == round((90 - 30) / 90 * 100)


def test_venetian_tilt_monotonic_decrease():
    """Higher sun elevation → lower tilt (slats more horizontal)."""
    tilts = [calculate_venetian_tilt(e) for e in range(5, 85, 10)]
    assert tilts == sorted(tilts, reverse=True)


def test_venetian_tilt_custom_min_max():
    """Custom min/max tilt limits are respected."""
    assert calculate_venetian_tilt(90, min_tilt=10, max_tilt=90) == 10
    assert calculate_venetian_tilt(0, min_tilt=10, max_tilt=90) == 90
    result = calculate_venetian_tilt(45, min_tilt=20, max_tilt=80)
    assert 20 <= result <= 80


def test_venetian_tilt_output_is_integer():
    """Result must always be an int (HA service expects int)."""
    for elev in range(0, 91, 5):
        assert isinstance(calculate_venetian_tilt(elev), int)
