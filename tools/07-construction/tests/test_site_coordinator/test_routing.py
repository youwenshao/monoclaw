"""Tests for SiteCoordinator routing."""

from construction.site_coordinator.routing.hk_geography import (
    HK_DISTRICTS,
    get_district_distance,
    get_travel_time,
)


def test_hk_districts_count():
    assert len(HK_DISTRICTS) == 18


def test_hk_districts_have_coordinates():
    for name, data in HK_DISTRICTS.items():
        assert "latitude" in data or "lat" in data
        assert "longitude" in data or "lng" in data or "lon" in data


def test_district_distance_same():
    dist = get_district_distance("Sha Tin", "Sha Tin")
    assert dist == 0 or dist < 1


def test_district_distance_cross_harbour():
    dist = get_district_distance("Central & Western", "Kwun Tong")
    assert dist > 0


def test_travel_time_peak():
    time_peak = get_travel_time("Central & Western", "Kwun Tong", "08:00")
    time_offpeak = get_travel_time("Central & Western", "Kwun Tong", "14:00")
    assert time_peak >= time_offpeak
