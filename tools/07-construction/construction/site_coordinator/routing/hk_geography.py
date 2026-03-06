"""Hong Kong 18-district geography data and distance utilities."""

from __future__ import annotations

import math
from typing import Any

HK_DISTRICTS: dict[str, dict[str, Any]] = {
    # Hong Kong Island
    "Central & Western": {"lat": 22.2860, "lng": 114.1500, "region": "HK Island"},
    "Eastern":           {"lat": 22.2840, "lng": 114.2240, "region": "HK Island"},
    "Southern":          {"lat": 22.2470, "lng": 114.1580, "region": "HK Island"},
    "Wan Chai":          {"lat": 22.2780, "lng": 114.1720, "region": "HK Island"},
    # Kowloon
    "Kowloon City":      {"lat": 22.3282, "lng": 114.1915, "region": "Kowloon"},
    "Kwun Tong":         {"lat": 22.3133, "lng": 114.2257, "region": "Kowloon"},
    "Sham Shui Po":      {"lat": 22.3308, "lng": 114.1625, "region": "Kowloon"},
    "Wong Tai Sin":      {"lat": 22.3420, "lng": 114.1932, "region": "Kowloon"},
    "Yau Tsim Mong":     {"lat": 22.3148, "lng": 114.1705, "region": "Kowloon"},
    # New Territories
    "Islands":           {"lat": 22.2610, "lng": 113.9465, "region": "NT"},
    "Kwai Tsing":        {"lat": 22.3544, "lng": 114.1310, "region": "NT"},
    "North":             {"lat": 22.4940, "lng": 114.1380, "region": "NT"},
    "Sai Kung":          {"lat": 22.3813, "lng": 114.2708, "region": "NT"},
    "Sha Tin":           {"lat": 22.3873, "lng": 114.1953, "region": "NT"},
    "Tai Po":            {"lat": 22.4513, "lng": 114.1686, "region": "NT"},
    "Tsuen Wan":         {"lat": 22.3710, "lng": 114.1134, "region": "NT"},
    "Tuen Mun":          {"lat": 22.3910, "lng": 113.9730, "region": "NT"},
    "Yuen Long":         {"lat": 22.4445, "lng": 114.0226, "region": "NT"},
}

# Pre-computed approximate road-distance offsets for cross-harbour routes (km).
# Actual driving distance is typically 1.3–1.6× the haversine distance within
# HK due to hilly terrain, tunnels, and one-way road systems.
_ROAD_FACTOR = 1.4

# Tunnel crossing overhead (km added for routing through a tunnel)
TUNNEL_OVERHEAD_KM: dict[str, float] = {
    "cross_harbour":   2.0,   # CHT / EHT via Hung Hom
    "western_harbour":  2.5,   # WHC via West Kowloon
    "eastern_harbour":  2.2,   # EHC via Kwun Tong
}


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _is_cross_harbour(from_d: dict, to_d: dict) -> bool:
    """True when one district is on HK Island and the other is not."""
    regions = {from_d["region"], to_d["region"]}
    return "HK Island" in regions and len(regions) > 1


def get_district_distance(from_district: str, to_district: str) -> float:
    """Approximate road distance in km between two HK districts."""
    if from_district == to_district:
        return 0.0

    fd = HK_DISTRICTS.get(from_district)
    td = HK_DISTRICTS.get(to_district)
    if not fd or not td:
        return 999.0

    dist = _haversine(fd["lat"], fd["lng"], td["lat"], td["lng"]) * _ROAD_FACTOR

    if _is_cross_harbour(fd, td):
        dist += TUNNEL_OVERHEAD_KM["cross_harbour"]

    return round(dist, 1)


def get_travel_time(
    from_district: str,
    to_district: str,
    departure_time: str = "",
) -> int:
    """Estimated travel time in minutes between two districts.

    Average speed assumptions:
    - Urban (HK Island / Kowloon): 20 km/h
    - Suburban / highway (NT): 35 km/h
    - Cross-region: 25 km/h
    Adds peak-hour congestion multiplier when *departure_time* is supplied.
    """
    dist = get_district_distance(from_district, to_district)
    if dist <= 0:
        return 0

    fd = HK_DISTRICTS.get(from_district, {})
    td = HK_DISTRICTS.get(to_district, {})

    urban = {"HK Island", "Kowloon"}
    if fd.get("region") in urban and td.get("region") in urban:
        speed = 20.0
    elif fd.get("region") == "NT" and td.get("region") == "NT":
        speed = 35.0
    else:
        speed = 25.0

    minutes = (dist / speed) * 60
    minutes = max(minutes, 5.0)

    if departure_time:
        multiplier = _peak_multiplier(departure_time)
        minutes *= multiplier

    return round(minutes)


def _peak_multiplier(departure_time: str) -> float:
    """Return congestion multiplier for the given HH:MM departure time."""
    try:
        parts = departure_time.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        t = hour + minute / 60.0
    except (ValueError, IndexError):
        return 1.0

    # Morning peak 07:30–09:30
    if 7.5 <= t <= 9.5:
        return 1.5
    # Evening peak 17:30–19:30
    if 17.5 <= t <= 19.5:
        return 1.6
    # Shoulder hours
    if (9.5 < t <= 10.5) or (17.0 <= t < 17.5):
        return 1.2
    return 1.0
