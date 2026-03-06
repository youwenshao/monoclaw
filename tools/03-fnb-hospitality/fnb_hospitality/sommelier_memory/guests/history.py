"""Visit logging, lifetime value calculation, average spend per head, and POS CSV import."""

from __future__ import annotations

import csv
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.fnb-hospitality.sommelier-memory.history")


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def log_visit(
    db_path: str | Path,
    guest_id: int,
    visit_date: str,
    party_size: int,
    total_spend: float,
    *,
    party_notes: str = "",
    table_number: str = "",
    wine_orders: str = "",
    food_highlights: str = "",
    staff_notes: str = "",
    rating: int | None = None,
    mona_db: str | Path | None = None,
) -> dict[str, Any]:
    with get_db(db_path) as conn:
        guest = conn.execute("SELECT id FROM sm_guests WHERE id = ?", (guest_id,)).fetchone()
        if not guest:
            raise ValueError(f"Guest {guest_id} not found")

        cursor = conn.execute(
            """INSERT INTO visits
               (guest_id, visit_date, party_size, party_notes, table_number,
                total_spend, wine_orders, food_highlights, staff_notes, rating)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (guest_id, visit_date, party_size, party_notes, table_number,
             total_spend, wine_orders, food_highlights, staff_notes, rating),
        )
        visit_id = cursor.lastrowid

        _refresh_guest_stats(conn, guest_id, visit_date)

        row = conn.execute("SELECT * FROM visits WHERE id = ?", (visit_id,)).fetchone()

    if mona_db:
        emit_event(
            mona_db,
            event_type="info",
            tool_name="sommelier-memory",
            summary=f"Visit logged for guest #{guest_id}: ${total_spend:.0f}, party of {party_size}",
        )

    return _row_to_dict(row)


def _refresh_guest_stats(
    conn: Any,
    guest_id: int,
    latest_visit_date: str | None = None,
) -> None:
    """Recalculate aggregated stats on sm_guests after a visit change."""
    stats = conn.execute(
        """SELECT COUNT(*) as cnt, COALESCE(SUM(total_spend), 0) as total,
                  COALESCE(SUM(total_spend) / NULLIF(SUM(party_size), 0), 0) as avg_per_head,
                  MIN(visit_date) as first_v, MAX(visit_date) as last_v
           FROM visits WHERE guest_id = ?""",
        (guest_id,),
    ).fetchone()

    conn.execute(
        """UPDATE sm_guests SET
               total_visits = ?, total_spend = ?, avg_spend_per_head = ?,
               first_visit = ?, last_visit = ?, updated_at = ?
           WHERE id = ?""",
        (stats[0], stats[1], round(stats[2], 2),
         stats[3], stats[4], datetime.now().isoformat(), guest_id),
    )


def get_visit_history(
    db_path: str | Path,
    guest_id: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM visits WHERE guest_id = ? ORDER BY visit_date DESC LIMIT ?",
            (guest_id, limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def calculate_lifetime_value(db_path: str | Path, guest_id: int) -> dict[str, Any]:
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) as visit_count,
                   COALESCE(SUM(total_spend), 0) as total_spend,
                   COALESCE(SUM(total_spend) / NULLIF(SUM(party_size), 0), 0) as avg_per_head,
                   COALESCE(AVG(total_spend), 0) as avg_per_visit,
                   COALESCE(AVG(party_size), 0) as avg_party_size,
                   MIN(visit_date) as first_visit,
                   MAX(visit_date) as last_visit
               FROM visits WHERE guest_id = ?""",
            (guest_id,),
        ).fetchone()

    if not row or row[0] == 0:
        return {
            "guest_id": guest_id,
            "visit_count": 0,
            "total_spend": 0.0,
            "avg_per_head": 0.0,
            "avg_per_visit": 0.0,
            "avg_party_size": 0.0,
            "first_visit": None,
            "last_visit": None,
        }

    return {
        "guest_id": guest_id,
        "visit_count": row[0],
        "total_spend": round(row[1], 2),
        "avg_per_head": round(row[2], 2),
        "avg_per_visit": round(row[3], 2),
        "avg_party_size": round(row[4], 1),
        "first_visit": row[5],
        "last_visit": row[6],
    }


def import_pos_csv(
    db_path: str | Path,
    csv_path: str | Path,
    *,
    mona_db: str | Path | None = None,
) -> int:
    """Import visit records from a POS CSV export.

    Expected CSV columns: phone, visit_date, party_size, total_spend,
    table_number (optional), wine_orders (optional), food_highlights (optional).

    Matches guests by phone number. Skips rows where no matching guest exists.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    imported = 0
    skipped = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows_to_insert: list[tuple[int, str, int, float, str, str, str]] = []

        with get_db(db_path) as conn:
            phone_to_id: dict[str, int] = {}
            for r in conn.execute("SELECT id, phone FROM sm_guests WHERE phone IS NOT NULL").fetchall():
                phone_to_id[r[1]] = r[0]

            for csv_row in reader:
                phone = csv_row.get("phone", "").strip()
                guest_id = phone_to_id.get(phone)
                if not guest_id:
                    skipped += 1
                    continue

                visit_date = csv_row.get("visit_date", date.today().isoformat()).strip()
                party_size = int(csv_row.get("party_size", 1))
                total_spend = float(csv_row.get("total_spend", 0))
                table_number = csv_row.get("table_number", "").strip()
                wine_orders = csv_row.get("wine_orders", "").strip()
                food_highlights = csv_row.get("food_highlights", "").strip()

                rows_to_insert.append(
                    (guest_id, visit_date, party_size, total_spend,
                     table_number, wine_orders, food_highlights)
                )

            for row_data in rows_to_insert:
                conn.execute(
                    """INSERT INTO visits
                       (guest_id, visit_date, party_size, total_spend,
                        table_number, wine_orders, food_highlights)
                       VALUES (?,?,?,?,?,?,?)""",
                    row_data,
                )
                imported += 1

            affected_guest_ids = {r[0] for r in rows_to_insert}
            for gid in affected_guest_ids:
                _refresh_guest_stats(conn, gid)

    logger.info("POS CSV import: %d imported, %d skipped from %s", imported, skipped, csv_path)

    if mona_db:
        emit_event(
            mona_db,
            event_type="action_completed",
            tool_name="sommelier-memory",
            summary=f"POS CSV imported: {imported} visits from {csv_path.name} ({skipped} skipped)",
        )

    return imported
