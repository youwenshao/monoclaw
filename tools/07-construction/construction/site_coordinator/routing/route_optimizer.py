"""Multi-site route optimiser for daily site visits."""

from __future__ import annotations

import logging
from typing import Any

from construction.site_coordinator.routing.hk_geography import (
    HK_DISTRICTS,
    get_district_distance,
    get_travel_time,
)
from construction.site_coordinator.routing.travel_time import estimate_travel_time

logger = logging.getLogger("openclaw.construction.site_coordinator.route_optimizer")


def optimize_route(
    sites: list[dict[str, Any]],
    start_district: str = "",
) -> dict[str, Any]:
    """Find a near-optimal visit sequence for *sites* minimizing total travel time.

    Each site dict should have at least ``district``, and optionally
    ``latitude``/``longitude`` for finer-grained estimation.

    Falls back to distance-based nearest-neighbour when no coordinates are
    available.
    """
    if not sites:
        return {"ordered_sites": [], "total_distance_km": 0, "total_time_minutes": 0}

    if len(sites) == 1:
        return {
            "ordered_sites": [_site_summary(sites[0], 0)],
            "total_distance_km": 0,
            "total_time_minutes": 0,
        }

    has_coords = all(
        s.get("latitude") is not None and s.get("longitude") is not None
        for s in sites
    )

    if has_coords:
        return _optimize_with_coords(sites, start_district)
    return _optimize_by_district(sites, start_district)


def _site_summary(site: dict, leg_minutes: int) -> dict[str, Any]:
    return {
        "site_id": site.get("id"),
        "site_name": site.get("site_name", ""),
        "district": site.get("district", ""),
        "leg_minutes": leg_minutes,
    }


def _optimize_by_district(
    sites: list[dict], start_district: str
) -> dict[str, Any]:
    """Nearest-neighbour heuristic using district-level distances."""
    remaining = list(sites)
    ordered: list[dict] = []
    total_dist = 0.0
    total_time = 0

    current_district = start_district or remaining[0].get("district", "")
    if not start_district:
        ordered.append(_site_summary(remaining.pop(0), 0))

    while remaining:
        best_idx = 0
        best_dist = float("inf")
        for i, s in enumerate(remaining):
            d = get_district_distance(current_district, s.get("district", ""))
            if d < best_dist:
                best_dist = d
                best_idx = i

        chosen = remaining.pop(best_idx)
        leg_time = get_travel_time(current_district, chosen.get("district", ""), "08:30")
        total_dist += best_dist
        total_time += leg_time
        ordered.append(_site_summary(chosen, leg_time))
        current_district = chosen.get("district", "")

    logger.info(
        "Route optimized (district): %d sites, %.1f km, %d min",
        len(ordered), total_dist, total_time,
    )
    return {
        "ordered_sites": ordered,
        "total_distance_km": round(total_dist, 1),
        "total_time_minutes": total_time,
    }


def _optimize_with_coords(
    sites: list[dict], start_district: str
) -> dict[str, Any]:
    """Nearest-neighbour heuristic using lat/lng coordinates."""
    remaining = list(sites)
    ordered: list[dict] = []
    total_dist = 0.0
    total_time = 0

    if start_district and start_district in HK_DISTRICTS:
        d_info = HK_DISTRICTS[start_district]
        current_lat, current_lng = d_info["lat"], d_info["lng"]
    else:
        first = remaining.pop(0)
        current_lat = first["latitude"]
        current_lng = first["longitude"]
        ordered.append(_site_summary(first, 0))

    while remaining:
        best_idx = 0
        best_dist = float("inf")

        for i, s in enumerate(remaining):
            from construction.site_coordinator.routing.hk_geography import _haversine
            d = _haversine(current_lat, current_lng, s["latitude"], s["longitude"])
            if d < best_dist:
                best_dist = d
                best_idx = i

        chosen = remaining.pop(best_idx)
        leg_time = estimate_travel_time(
            (current_lat, current_lng),
            (chosen["latitude"], chosen["longitude"]),
            "08:30",
        )
        road_dist = best_dist * 1.4
        total_dist += road_dist
        total_time += leg_time
        ordered.append(_site_summary(chosen, leg_time))
        current_lat = chosen["latitude"]
        current_lng = chosen["longitude"]

    logger.info(
        "Route optimized (coords): %d sites, %.1f km, %d min",
        len(ordered), total_dist, total_time,
    )
    return {
        "ordered_sites": ordered,
        "total_distance_km": round(total_dist, 1),
        "total_time_minutes": total_time,
    }
