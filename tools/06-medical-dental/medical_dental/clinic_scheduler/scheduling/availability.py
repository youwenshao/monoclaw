"""Interval-based availability engine for the ClinicScheduler."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.scheduler.availability")

BUFFER_MINUTES = 5
CACHE_TTL_SECONDS = 60


class _SlotCache:
    """Simple in-memory TTL cache keyed by (doctor_id, date, service_type)."""

    def __init__(self, ttl: int = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._store: dict[tuple, tuple[float, list[dict[str, str]]]] = {}

    def get(self, key: tuple) -> list[dict[str, str]] | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[key]
            return None
        return data

    def put(self, key: tuple, data: list[dict[str, str]]) -> None:
        self._store[key] = (time.monotonic(), data)

    def invalidate(self, doctor_id: int | None = None) -> None:
        if doctor_id is None:
            self._store.clear()
            return
        self._store = {k: v for k, v in self._store.items() if k[0] != doctor_id}


_cache = _SlotCache()


def _time_to_minutes(t: str) -> int:
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _minutes_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _get_service_duration(db_path: str | Path, doctor_id: int, service_type: str | None, config_durations: dict[str, int] | None = None) -> int:
    durations = config_durations or {}
    if service_type and service_type in durations:
        return durations[service_type]

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT default_slot_duration FROM doctors WHERE id = ?", (doctor_id,)
        ).fetchone()
    return row["default_slot_duration"] if row else 15


def _is_public_holiday(target_date: date, holidays: list[str]) -> bool:
    iso = target_date.isoformat()
    return iso in holidays


class AvailabilityEngine:
    """Computes available appointment slots using interval subtraction."""

    def __init__(self, holidays: list[str] | None = None, config_durations: dict[str, int] | None = None) -> None:
        self._holidays = holidays or []
        self._config_durations = config_durations or {}

    def get_available_slots(
        self,
        db_path: str | Path,
        doctor_id: int,
        target_date: date,
        service_type: str | None = None,
    ) -> list[dict[str, str]]:
        if _is_public_holiday(target_date, self._holidays):
            return []

        cache_key = (doctor_id, target_date.isoformat(), service_type or "")
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        duration = _get_service_duration(db_path, doctor_id, service_type, self._config_durations)
        work_intervals = self._get_work_intervals(db_path, doctor_id, target_date)
        if not work_intervals:
            return []

        booked_intervals = self._get_booked_intervals(db_path, doctor_id, target_date)
        free_intervals = self._subtract_intervals(work_intervals, booked_intervals)

        slots: list[dict[str, str]] = []
        room_map = self._get_room_map(db_path, doctor_id, target_date)

        for start_m, end_m in free_intervals:
            cursor = start_m
            while cursor + duration <= end_m:
                slot_start = _minutes_to_time(cursor)
                slot_end = _minutes_to_time(cursor + duration)
                room = self._resolve_room(cursor, room_map)
                slots.append({
                    "start_time": slot_start,
                    "end_time": slot_end,
                    "room": room,
                })
                cursor += duration + BUFFER_MINUTES

        _cache.put(cache_key, slots)
        return slots

    def is_slot_available(
        self,
        db_path: str | Path,
        doctor_id: int,
        target_date: date,
        start_time: str,
        end_time: str,
    ) -> bool:
        if _is_public_holiday(target_date, self._holidays):
            return False

        start_m = _time_to_minutes(start_time)
        end_m = _time_to_minutes(end_time)

        work_intervals = self._get_work_intervals(db_path, doctor_id, target_date)
        in_schedule = any(ws <= start_m and end_m <= we for ws, we in work_intervals)
        if not in_schedule:
            return False

        booked_intervals = self._get_booked_intervals(db_path, doctor_id, target_date)
        for bs, be in booked_intervals:
            if start_m < be and end_m > bs:
                return False

        return True

    def get_daily_schedule(
        self,
        db_path: str | Path,
        doctor_id: int,
        target_date: date,
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []

        work_intervals = self._get_work_intervals(db_path, doctor_id, target_date)
        for ws, we in work_intervals:
            entries.append({
                "type": "working_hours",
                "start_time": _minutes_to_time(ws),
                "end_time": _minutes_to_time(we),
            })

        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT id, patient_name, patient_phone, service_type,
                          start_time, end_time, room, status
                   FROM appointments
                   WHERE doctor_id = ? AND appointment_date = ? AND status != 'cancelled'
                   ORDER BY start_time""",
                (doctor_id, target_date.isoformat()),
            ).fetchall()

        for row in rows:
            r = dict(row)
            entries.append({
                "type": "appointment",
                "appointment_id": r["id"],
                "patient_name": r["patient_name"],
                "patient_phone": r["patient_phone"],
                "service_type": r["service_type"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "room": r["room"],
                "status": r["status"],
            })

        entries.sort(key=lambda e: e["start_time"])
        return entries

    def invalidate_cache(self, doctor_id: int | None = None) -> None:
        _cache.invalidate(doctor_id)

    # ------------------------------------------------------------------

    def _get_work_intervals(self, db_path: str | Path, doctor_id: int, target_date: date) -> list[tuple[int, int]]:
        dow = target_date.isoweekday() % 7
        iso = target_date.isoformat()

        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT start_time, end_time FROM schedules
                   WHERE doctor_id = ? AND day_of_week = ?
                     AND (effective_from IS NULL OR effective_from <= ?)
                     AND (effective_until IS NULL OR effective_until >= ?)
                   ORDER BY start_time""",
                (doctor_id, dow, iso, iso),
            ).fetchall()

        return [(_time_to_minutes(r["start_time"]), _time_to_minutes(r["end_time"])) for r in rows]

    def _get_booked_intervals(self, db_path: str | Path, doctor_id: int, target_date: date) -> list[tuple[int, int]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT start_time, end_time FROM appointments
                   WHERE doctor_id = ? AND appointment_date = ? AND status NOT IN ('cancelled')
                   ORDER BY start_time""",
                (doctor_id, target_date.isoformat()),
            ).fetchall()

        intervals: list[tuple[int, int]] = []
        for r in rows:
            s = _time_to_minutes(r["start_time"])
            e = _time_to_minutes(r["end_time"]) + BUFFER_MINUTES
            intervals.append((s, e))
        return intervals

    @staticmethod
    def _subtract_intervals(
        work: list[tuple[int, int]],
        booked: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        free: list[tuple[int, int]] = list(work)
        for bs, be in booked:
            new_free: list[tuple[int, int]] = []
            for fs, fe in free:
                if be <= fs or bs >= fe:
                    new_free.append((fs, fe))
                else:
                    if fs < bs:
                        new_free.append((fs, bs))
                    if be < fe:
                        new_free.append((be, fe))
            free = new_free
        return free

    def _get_room_map(self, db_path: str | Path, doctor_id: int, target_date: date) -> list[tuple[int, int, str]]:
        dow = target_date.isoweekday() % 7
        iso = target_date.isoformat()

        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT start_time, end_time, room FROM schedules
                   WHERE doctor_id = ? AND day_of_week = ?
                     AND (effective_from IS NULL OR effective_from <= ?)
                     AND (effective_until IS NULL OR effective_until >= ?)
                   ORDER BY start_time""",
                (doctor_id, dow, iso, iso),
            ).fetchall()

        return [(_time_to_minutes(r["start_time"]), _time_to_minutes(r["end_time"]), r["room"] or "") for r in rows]

    @staticmethod
    def _resolve_room(minute: int, room_map: list[tuple[int, int, str]]) -> str:
        for start, end, room in room_map:
            if start <= minute < end:
                return room
        return ""
