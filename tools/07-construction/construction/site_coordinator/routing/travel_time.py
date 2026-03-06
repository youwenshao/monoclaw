"""Time-of-day travel estimation between coordinate pairs."""

from __future__ import annotations

import logging
import math

logger = logging.getLogger("openclaw.construction.site_coordinator.travel_time")

# Average speeds in km/h for HK road network
_BASE_SPEED_KMH = 25.0
_ROAD_FACTOR = 1.4

# Peak congestion windows
_MORNING_PEAK = (7.5, 9.5)
_EVENING_PEAK = (17.5, 19.5)
_MORNING_MULTIPLIER = 1.5
_EVENING_MULTIPLIER = 1.6
_SHOULDER_MULTIPLIER = 1.2

# Cross-harbour threshold: if one point is south of ~22.30 (HK Island)
# and the other is north, add tunnel delay.
_HARBOUR_LAT = 22.30
_TUNNEL_DELAY_MINUTES = 8


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_time(departure_time: str) -> float | None:
    """Parse HH:MM into fractional hours. Returns None on failure."""
    try:
        parts = departure_time.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        return hour + minute / 60.0
    except (ValueError, IndexError):
        return None


def _congestion_multiplier(t: float) -> float:
    if _MORNING_PEAK[0] <= t <= _MORNING_PEAK[1]:
        return _MORNING_MULTIPLIER
    if _EVENING_PEAK[0] <= t <= _EVENING_PEAK[1]:
        return _EVENING_MULTIPLIER
    if (9.5 < t <= 10.5) or (17.0 <= t < 17.5):
        return _SHOULDER_MULTIPLIER
    return 1.0


def _crosses_harbour(lat1: float, lat2: float) -> bool:
    return (lat1 < _HARBOUR_LAT) != (lat2 < _HARBOUR_LAT)


def estimate_travel_time(
    from_coords: tuple[float, float],
    to_coords: tuple[float, float],
    departure_time: str,
) -> int:
    """Estimate travel time in minutes between two (lat, lng) points.

    Factors in:
    - Road distance (haversine × road factor)
    - Peak-hour congestion multipliers
    - Cross-harbour tunnel delay
    """
    lat1, lng1 = from_coords
    lat2, lng2 = to_coords

    dist = _haversine_km(lat1, lng1, lat2, lng2) * _ROAD_FACTOR
    if dist < 0.1:
        return 0

    base_minutes = (dist / _BASE_SPEED_KMH) * 60

    t = _parse_time(departure_time)
    if t is not None:
        base_minutes *= _congestion_multiplier(t)

    if _crosses_harbour(lat1, lat2):
        base_minutes += _TUNNEL_DELAY_MINUTES
        logger.debug(
            "Cross-harbour route detected, added %d min tunnel delay",
            _TUNNEL_DELAY_MINUTES,
        )

    return max(round(base_minutes), 3)
