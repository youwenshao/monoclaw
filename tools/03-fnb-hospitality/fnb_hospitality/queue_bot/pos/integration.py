"""POS data integration via CSV import.

Expected CSV columns: table, covers, open_time, close_time
Populates the table_turnover table used by the wait-time estimator.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

REQUIRED_COLUMNS = {"table", "covers", "open_time", "close_time"}


def _parse_duration(open_time: str, close_time: str) -> int | None:
    """Calculate duration in minutes between open and close times."""
    fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M")
    for fmt in fmts:
        try:
            t_open = datetime.strptime(open_time.strip(), fmt)
            t_close = datetime.strptime(close_time.strip(), fmt)
            delta = (t_close - t_open).total_seconds() / 60
            return int(delta) if delta > 0 else None
        except ValueError:
            continue
    return None


def _infer_time_slot(open_time: str) -> str:
    """Infer dining session from the open time."""
    fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M")
    for fmt in fmts:
        try:
            t = datetime.strptime(open_time.strip(), fmt)
            return "lunch" if t.hour < 15 else "dinner"
        except ValueError:
            continue
    return "dinner"


def _infer_date(open_time: str) -> str:
    """Extract date from a datetime string, or use today."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(open_time.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")


def import_csv(db_path: str | Path, csv_content: str) -> dict:
    """Import POS turnover data from CSV content.

    Returns a summary dict with imported/skipped counts and error messages.
    """
    reader = csv.DictReader(io.StringIO(csv_content))
    if not reader.fieldnames:
        raise ValueError("CSV file has no header row")

    normalised = {f.strip().lower() for f in reader.fieldnames}
    missing = REQUIRED_COLUMNS - normalised
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    field_map = {f: f.strip().lower() for f in reader.fieldnames}

    imported = 0
    skipped = 0
    errors: list[str] = []

    with get_db(db_path) as conn:
        for line_no, raw_row in enumerate(reader, start=2):
            row = {field_map[k]: v for k, v in raw_row.items()}
            try:
                table_id = row["table"].strip()
                covers = int(row["covers"].strip())
                open_time = row["open_time"].strip()
                close_time = row["close_time"].strip()

                duration = _parse_duration(open_time, close_time)
                if duration is None or duration <= 0:
                    skipped += 1
                    errors.append(f"Row {line_no}: invalid duration")
                    continue

                d = _infer_date(open_time)
                slot = _infer_time_slot(open_time)

                conn.execute(
                    """INSERT INTO table_turnover
                       (date, time_slot, table_id, party_size,
                        seated_at, cleared_at, duration_minutes, source)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (d, slot, table_id, covers, open_time, close_time, duration, "pos"),
                )
                imported += 1
            except (KeyError, ValueError) as exc:
                skipped += 1
                errors.append(f"Row {line_no}: {exc}")

    return {"imported": imported, "skipped": skipped, "errors": errors[:20]}
