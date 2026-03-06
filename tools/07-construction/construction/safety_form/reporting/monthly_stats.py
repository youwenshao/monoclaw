"""Monthly safety KPI statistics and trend analysis."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.safety_form.reporting.stats")


def calculate_monthly_stats(db_path: str | Path, site_id: int, month: str) -> dict:
    """Calculate monthly safety KPIs for a site.

    Parameters:
        db_path: Path to the safety_form database
        site_id: Site to compute stats for
        month: ISO month string, e.g. '2025-03'

    Returns a dict with:
        - accident_frequency_rate (AFR)
        - incident_rate
        - safety_training_hours
        - near_miss_reporting_rate
        - inspection_coverage
        - average_inspection_score
        - deficiency_closure_rate
        - days_without_accident
    """
    month_start = f"{month}-01"
    try:
        next_month = _next_month(month)
    except (ValueError, IndexError):
        logger.error("Invalid month format: %s", month)
        return {}

    with get_db(db_path) as conn:
        # Total worker-hours (estimated from daily worker counts * 8-hour day)
        worker_rows = conn.execute(
            "SELECT COALESCE(SUM(worker_count), 0) as total_workers FROM daily_inspections "
            "WHERE site_id = ? AND inspection_date >= ? AND inspection_date < ?",
            (site_id, month_start, next_month),
        ).fetchone()
        total_worker_days = worker_rows["total_workers"] or 0
        total_worker_hours = total_worker_days * 8

        # Accidents in the month
        accident_count = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE site_id = ? AND incident_type = 'accident' "
            "AND date_time >= ? AND date_time < ?",
            (site_id, month_start, next_month),
        ).fetchone()[0]

        # All incidents
        total_incidents = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE site_id = ? "
            "AND date_time >= ? AND date_time < ?",
            (site_id, month_start, next_month),
        ).fetchone()[0]

        # Near misses
        near_misses = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE site_id = ? AND incident_type = 'near_miss' "
            "AND date_time >= ? AND date_time < ?",
            (site_id, month_start, next_month),
        ).fetchone()[0]

        # Toolbox talks (proxy for safety training hours)
        talks = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) as total_mins, "
            "COALESCE(SUM(attendee_count), 0) as total_attendees "
            "FROM toolbox_talks WHERE site_id = ? AND talk_date >= ? AND talk_date < ?",
            (site_id, month_start, next_month),
        ).fetchone()
        training_minutes = talks["total_mins"] or 0
        training_hours = round(training_minutes / 60.0, 1)

        # Inspections
        inspections = conn.execute(
            "SELECT COUNT(*) as total, "
            "COALESCE(AVG(overall_score), 0) as avg_score "
            "FROM daily_inspections WHERE site_id = ? AND status = 'completed' "
            "AND inspection_date >= ? AND inspection_date < ?",
            (site_id, month_start, next_month),
        ).fetchone()
        inspection_count = inspections["total"] or 0
        avg_score = inspections["avg_score"] or 0

        # Working days in month (approx 26 days, 6-day HK construction week)
        working_days = _working_days_in_month(month)
        inspection_coverage = (inspection_count / working_days * 100) if working_days else 0

        # Deficiency closure rate
        opened = conn.execute(
            "SELECT COUNT(*) FROM deficiencies WHERE site_id = ? "
            "AND reported_date >= ? AND reported_date < ?",
            (site_id, month_start, next_month),
        ).fetchone()[0]
        closed = conn.execute(
            "SELECT COUNT(*) FROM deficiencies WHERE site_id = ? "
            "AND resolved_date >= ? AND resolved_date < ?",
            (site_id, month_start, next_month),
        ).fetchone()[0]
        closure_rate = (closed / opened * 100) if opened else 100.0

        # Days without accident (from month start or last accident)
        last_accident = conn.execute(
            "SELECT MAX(date_time) as last_dt FROM incidents "
            "WHERE site_id = ? AND incident_type = 'accident'",
            (site_id,),
        ).fetchone()
        last_accident_dt = last_accident["last_dt"] if last_accident else None

        if last_accident_dt:
            try:
                last_dt = datetime.fromisoformat(last_accident_dt)
                days_safe = (datetime.now() - last_dt).days
            except (ValueError, TypeError):
                days_safe = 0
        else:
            days_safe = 365  # no accidents on record

    # Accident Frequency Rate = (accidents * 1,000,000) / total worker-hours
    afr = (accident_count * 1_000_000 / total_worker_hours) if total_worker_hours else 0
    # Incident Rate = (total incidents * 200,000) / total worker-hours (OSHA formula)
    incident_rate = (total_incidents * 200_000 / total_worker_hours) if total_worker_hours else 0
    # Near-miss ratio relative to total incidents
    near_miss_rate = (near_misses / total_incidents * 100) if total_incidents else 0

    stats = {
        "site_id": site_id,
        "month": month,
        "accident_frequency_rate": round(afr, 2),
        "incident_rate": round(incident_rate, 2),
        "total_incidents": total_incidents,
        "accidents": accident_count,
        "near_misses": near_misses,
        "near_miss_reporting_rate": round(near_miss_rate, 1),
        "safety_training_hours": training_hours,
        "training_attendees": talks["total_attendees"] or 0,
        "inspection_count": inspection_count,
        "inspection_coverage": round(inspection_coverage, 1),
        "average_inspection_score": round(avg_score, 1),
        "deficiencies_opened": opened,
        "deficiencies_closed": closed,
        "deficiency_closure_rate": round(closure_rate, 1),
        "days_without_accident": days_safe,
        "total_worker_hours": total_worker_hours,
    }

    logger.info("Monthly stats for site %d (%s): AFR=%.2f, score=%.1f%%", site_id, month, afr, avg_score)
    return stats


def _next_month(month: str) -> str:
    """Given '2025-03', return '2025-04'."""
    parts = month.split("-")
    year, mon = int(parts[0]), int(parts[1])
    if mon == 12:
        return f"{year + 1}-01"
    return f"{year}-{mon + 1:02d}"


def _working_days_in_month(month: str) -> int:
    """Estimate working days (6-day week, HK construction standard)."""
    parts = month.split("-")
    year, mon = int(parts[0]), int(parts[1])
    d = date(year, mon, 1)
    count = 0
    while d.month == mon:
        if d.weekday() != 6:  # Sunday off
            count += 1
        d += timedelta(days=1)
    return count
