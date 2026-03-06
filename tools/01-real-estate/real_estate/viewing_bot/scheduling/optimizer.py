"""Route optimizer for daily viewing schedules using nearest-neighbour heuristic."""

from __future__ import annotations

import math
from typing import Any

HK_DISTRICT_COORDS: dict[str, tuple[float, float]] = {
    "Central & Western": (22.2860, 114.1500),
    "Wan Chai": (22.2780, 114.1720),
    "Eastern": (22.2840, 114.2240),
    "Southern": (22.2470, 114.1580),
    "Yau Tsim Mong": (22.3120, 114.1720),
    "Sham Shui Po": (22.3300, 114.1590),
    "Kowloon City": (22.3280, 114.1910),
    "Wong Tai Sin": (22.3420, 114.1940),
    "Kwun Tong": (22.3130, 114.2260),
    "Sha Tin": (22.3810, 114.1880),
    "Tai Po": (22.4510, 114.1640),
    "North": (22.4960, 114.1380),
    "Tuen Mun": (22.3910, 113.9770),
    "Yuen Long": (22.4440, 114.0220),
    "Tsuen Wan": (22.3710, 114.1140),
    "Kwai Tsing": (22.3560, 114.1310),
    "Islands": (22.2620, 113.9460),
    "Sai Kung": (22.3820, 114.2710),
}

EARTH_RADIUS_KM = 6371.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometres."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_coords(viewing: dict[str, Any]) -> tuple[float, float]:
    """Extract or look up coordinates for a viewing."""
    if viewing.get("lat") and viewing.get("lon"):
        return float(viewing["lat"]), float(viewing["lon"])
    district = viewing.get("district", "")
    return HK_DISTRICT_COORDS.get(district, (22.3193, 114.1694))


def optimize_route(viewings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Order viewings using a nearest-neighbour heuristic to minimise travel.

    Each viewing dict should contain at minimum: id, district, proposed_datetime.
    Optionally lat/lon for precise coordinates.

    Returns the input list reordered with added fields:
      - route_order: int (1-indexed)
      - distance_from_prev_km: float
      - cumulative_distance_km: float
    """
    if not viewings:
        return []
    if len(viewings) == 1:
        v = dict(viewings[0])
        v["route_order"] = 1
        v["distance_from_prev_km"] = 0.0
        v["cumulative_distance_km"] = 0.0
        return [v]

    remaining = list(range(len(viewings)))
    coords = [_get_coords(v) for v in viewings]

    ordered_indices: list[int] = []
    current = _pick_starting_point(viewings, remaining)
    ordered_indices.append(current)
    remaining.remove(current)

    while remaining:
        nearest_idx = min(
            remaining,
            key=lambda i: haversine_distance(*coords[current], *coords[i]),
        )
        ordered_indices.append(nearest_idx)
        remaining.remove(nearest_idx)
        current = nearest_idx

    result: list[dict[str, Any]] = []
    cumulative = 0.0
    for order, idx in enumerate(ordered_indices, 1):
        v = dict(viewings[idx])
        if order == 1:
            dist = 0.0
        else:
            prev_idx = ordered_indices[order - 2]
            dist = haversine_distance(*coords[prev_idx], *coords[idx])
        cumulative += dist
        v["route_order"] = order
        v["distance_from_prev_km"] = round(dist, 2)
        v["cumulative_distance_km"] = round(cumulative, 2)
        result.append(v)

    return result


def _pick_starting_point(viewings: list[dict[str, Any]], indices: list[int]) -> int:
    """Pick the viewing with the earliest proposed time as the starting point."""
    return min(indices, key=lambda i: viewings[i].get("proposed_datetime", ""))
