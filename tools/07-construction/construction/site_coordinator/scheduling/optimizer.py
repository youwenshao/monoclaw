"""OR-Tools CP-SAT schedule optimizer with graceful fallback."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from construction.site_coordinator.scheduling.trade_dependencies import TRADE_DEPENDENCIES

logger = logging.getLogger("openclaw.construction.site_coordinator.optimizer")

try:
    from ortools.sat.python import cp_model  # type: ignore[import-untyped]

    HAS_ORTOOLS = True
except ImportError:
    HAS_ORTOOLS = False
    logger.info("OR-Tools not installed — using greedy fallback scheduler")


# Noise permit hours in HK: typically 07:00–19:00 weekdays
NOISE_PERMIT_START = 7
NOISE_PERMIT_END = 19


def optimize_day(
    db_path: str | Path,
    target_date: str,
    config: Any,
) -> dict[str, Any]:
    """Optimize the schedule for *target_date*.

    Uses OR-Tools CP-SAT solver when available, otherwise falls back to a
    greedy heuristic.  Returns a dict with ``assignments_created`` count and
    ``assignments`` detail list.
    """
    sites, contractors, existing = _load_data(db_path, target_date)

    if not sites or not contractors:
        return {"assignments_created": 0, "assignments": [], "note": "No active sites or contractors"}

    sc_config = getattr(config, "extra", {}).get("site_coordinator", {}) if config else {}

    if HAS_ORTOOLS:
        return _solve_cpsat(db_path, target_date, sites, contractors, existing, sc_config)
    return _greedy_fallback(db_path, target_date, sites, contractors, existing, sc_config)


def _load_data(
    db_path: str | Path, target_date: str
) -> tuple[list[dict], list[dict], list[dict]]:
    with get_db(db_path) as conn:
        sites = [dict(r) for r in conn.execute(
            "SELECT * FROM sites WHERE status = 'active'"
        ).fetchall()]
        contractors = [dict(r) for r in conn.execute(
            "SELECT * FROM contractors WHERE active = TRUE"
        ).fetchall()]
        existing = [dict(r) for r in conn.execute(
            "SELECT * FROM schedule_assignments "
            "WHERE assignment_date = ? AND status NOT IN ('cancelled', 'rescheduled')",
            (target_date,),
        ).fetchall()]
    return sites, contractors, existing


def _solve_cpsat(
    db_path: str | Path,
    target_date: str,
    sites: list[dict],
    contractors: list[dict],
    existing: list[dict],
    sc_config: dict,
) -> dict[str, Any]:
    """Build and solve a CP-SAT model for daily assignment scheduling."""
    model = cp_model.CpModel()

    site_ids = [s["id"] for s in sites]
    contractor_ids = [c["id"] for c in contractors]
    site_map = {s["id"]: s for s in sites}
    contractor_map = {c["id"]: c for c in contractors}

    already_assigned: set[int] = {a["contractor_id"] for a in existing}

    # Decision variables: assign[c, s] = 1 if contractor c goes to site s
    assign: dict[tuple[int, int], Any] = {}
    for c_id in contractor_ids:
        for s_id in site_ids:
            assign[(c_id, s_id)] = model.NewBoolVar(f"assign_c{c_id}_s{s_id}")

    # Each contractor assigned to at most one site per day
    for c_id in contractor_ids:
        model.Add(sum(assign[(c_id, s_id)] for s_id in site_ids) <= 1)
        if c_id in already_assigned:
            for s_id in site_ids:
                model.Add(assign[(c_id, s_id)] == 0)

    # Site capacity constraints
    for s_id in site_ids:
        max_workers = site_map[s_id].get("max_daily_workers", 20)
        already_at_site = sum(1 for a in existing if a["site_id"] == s_id)
        remaining = max(0, max_workers - already_at_site)
        model.Add(sum(assign[(c_id, s_id)] for c_id in contractor_ids) <= remaining)

    # Noise permit: check if target_date is within noise hours (weekday check)
    target_dt = datetime.fromisoformat(target_date)
    is_weekday = target_dt.weekday() < 5
    noisy_trades = {"demolition", "piling", "excavation", "concreting"}

    if not is_weekday:
        for c_id in contractor_ids:
            c_trade = contractor_map[c_id].get("trade", "").lower()
            if c_trade in noisy_trades:
                for s_id in site_ids:
                    model.Add(assign[(c_id, s_id)] == 0)

    # Trade dependency soft constraints via priorities
    priorities: dict[tuple[int, int], int] = {}
    for c_id in contractor_ids:
        c_trade = contractor_map[c_id].get("trade", "").lower()
        for s_id in site_ids:
            priority = 1
            required_deps = TRADE_DEPENDENCIES.get(c_trade, [])
            if not required_deps:
                priority = 3
            priorities[(c_id, s_id)] = priority

    # Maximize total assignments weighted by priority
    model.Maximize(
        sum(assign[(c_id, s_id)] * priorities.get((c_id, s_id), 1)
            for c_id in contractor_ids for s_id in site_ids)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)

    assignments_created = 0
    assignments: list[dict] = []

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        with get_db(db_path) as conn:
            for c_id in contractor_ids:
                for s_id in site_ids:
                    if solver.Value(assign[(c_id, s_id)]) == 1:
                        c = contractor_map[c_id]
                        start_time = "08:00" if is_weekday else "09:00"
                        end_time = "18:00" if is_weekday else "17:00"

                        conn.execute(
                            "INSERT INTO schedule_assignments "
                            "(site_id, contractor_id, assignment_date, start_time, end_time, "
                            "trade, status, priority) VALUES (?,?,?,?,?,?,?,?)",
                            (s_id, c_id, target_date, start_time, end_time,
                             c.get("trade", ""), "scheduled", 5),
                        )
                        assignments_created += 1
                        assignments.append({
                            "contractor_id": c_id,
                            "site_id": s_id,
                            "company": c.get("company_name", ""),
                            "trade": c.get("trade", ""),
                        })

        logger.info(
            "CP-SAT solved for %s: %d assignments (status=%s)",
            target_date, assignments_created,
            "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        )
    else:
        logger.warning("CP-SAT found no feasible solution for %s", target_date)

    return {"assignments_created": assignments_created, "assignments": assignments, "solver": "cpsat"}


def _greedy_fallback(
    db_path: str | Path,
    target_date: str,
    sites: list[dict],
    contractors: list[dict],
    existing: list[dict],
    sc_config: dict,
) -> dict[str, Any]:
    """Simple greedy scheduler used when OR-Tools is not available."""
    already_assigned: set[int] = {a["contractor_id"] for a in existing}
    site_counts: dict[int, int] = {}
    for a in existing:
        site_counts[a["site_id"]] = site_counts.get(a["site_id"], 0) + 1

    target_dt = datetime.fromisoformat(target_date)
    is_weekday = target_dt.weekday() < 5
    noisy_trades = {"demolition", "piling", "excavation", "concreting"}

    available = [
        c for c in contractors
        if c["id"] not in already_assigned
        and (is_weekday or c.get("trade", "").lower() not in noisy_trades)
    ]

    assignments_created = 0
    assignments: list[dict] = []

    with get_db(db_path) as conn:
        for contractor in available:
            best_site = None
            best_gap = -1

            for site in sites:
                max_w = site.get("max_daily_workers", 20)
                current = site_counts.get(site["id"], 0)
                gap = max_w - current
                if gap > best_gap:
                    best_gap = gap
                    best_site = site

            if best_site and best_gap > 0:
                start_time = "08:00" if is_weekday else "09:00"
                end_time = "18:00" if is_weekday else "17:00"

                conn.execute(
                    "INSERT INTO schedule_assignments "
                    "(site_id, contractor_id, assignment_date, start_time, end_time, "
                    "trade, status, priority) VALUES (?,?,?,?,?,?,?,?)",
                    (best_site["id"], contractor["id"], target_date,
                     start_time, end_time, contractor.get("trade", ""), "scheduled", 5),
                )
                site_counts[best_site["id"]] = site_counts.get(best_site["id"], 0) + 1
                assignments_created += 1
                assignments.append({
                    "contractor_id": contractor["id"],
                    "site_id": best_site["id"],
                    "company": contractor.get("company_name", ""),
                    "trade": contractor.get("trade", ""),
                })

    logger.info("Greedy fallback for %s: %d assignments", target_date, assignments_created)
    return {"assignments_created": assignments_created, "assignments": assignments, "solver": "greedy"}
