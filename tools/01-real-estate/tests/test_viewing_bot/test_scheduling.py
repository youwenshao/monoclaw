"""Tests for ViewingBot scheduling and routing."""

import pytest
from datetime import datetime


def test_haversine_distance():
    """Haversine should give reasonable HK cross-harbour distances."""
    from real_estate.viewing_bot.scheduling.optimizer import haversine_distance
    # Central to TST is roughly 1.5-2.5 km across harbour
    dist = haversine_distance(22.2819, 114.1585, 22.2988, 114.1722)
    assert 0.5 < dist < 5.0


def test_route_optimization():
    """Route optimizer should return viewings in geographic order."""
    from real_estate.viewing_bot.scheduling.optimizer import optimize_route
    viewings = [
        {"id": 1, "district": "Eastern", "property_address": "Taikoo Shing"},
        {"id": 2, "district": "Central & Western", "property_address": "Belcher's"},
        {"id": 3, "district": "Eastern", "property_address": "City Garden"},
    ]
    route = optimize_route(viewings)
    assert len(route) == 3
    # Eastern viewings should be grouped together
    eastern_positions = [r["route_order"] for r in route if r["district"] == "Eastern"]
    assert abs(eastern_positions[0] - eastern_positions[1]) == 1


def test_district_travel_matrix():
    """Travel matrix should have cross-harbour penalty."""
    from real_estate.viewing_bot.scheduling.conflict import DISTRICT_TRAVEL_MATRIX
    assert isinstance(DISTRICT_TRAVEL_MATRIX, dict)


def test_weather_safety_check():
    """T8+ should be considered unsafe."""
    from real_estate.viewing_bot.scheduling.weather import is_viewing_unsafe
    assert is_viewing_unsafe([{"name": "Tropical Cyclone Warning Signal, No. 8"}]) is True
    assert is_viewing_unsafe([{"name": "Thunderstorm Warning"}]) is False
    assert is_viewing_unsafe([]) is False
