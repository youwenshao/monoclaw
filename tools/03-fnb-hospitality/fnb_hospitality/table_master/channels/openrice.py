"""OpenRice integration — API-first with HTTP scraping fallback."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

logger = logging.getLogger("openclaw.table_master.channels.openrice")


async def poll_openrice_bookings(
    *,
    api_key: str,
    restaurant_id: str,
    db_path: str,
    mona_db_path: str,
) -> list[dict[str, Any]]:
    """Fetch new bookings from OpenRice.

    Attempts the official API first; falls back to scraping the partner
    dashboard page if the API is unavailable.
    """
    if api_key:
        return await _fetch_via_api(
            api_key=api_key,
            restaurant_id=restaurant_id,
            db_path=db_path,
            mona_db_path=mona_db_path,
        )
    return await _fetch_via_scraping(
        restaurant_id=restaurant_id,
        db_path=db_path,
        mona_db_path=mona_db_path,
    )


async def _fetch_via_api(
    *,
    api_key: str,
    restaurant_id: str,
    db_path: str,
    mona_db_path: str,
) -> list[dict[str, Any]]:
    """Pull bookings from the OpenRice partner API."""
    import httpx

    url = f"https://api.openrice.com/partner/v1/restaurants/{restaurant_id}/bookings"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    created: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("OpenRice API failed, falling back to scraping: %s", exc)
        return await _fetch_via_scraping(
            restaurant_id=restaurant_id,
            db_path=db_path,
            mona_db_path=mona_db_path,
        )

    for item in data.get("bookings", []):
        ref = item.get("booking_ref", "")
        if _already_imported(db_path, channel_ref=ref):
            continue

        booking = _import_booking(
            db_path=db_path,
            mona_db_path=mona_db_path,
            guest_name=item.get("guest_name", "OpenRice Guest"),
            guest_phone=item.get("guest_phone", ""),
            party_size=item.get("party_size", 2),
            booking_date=item.get("date", ""),
            booking_time=item.get("time", "19:00"),
            channel_ref=ref,
            special_requests=item.get("remarks", ""),
        )
        created.append(booking)

    return created


async def _fetch_via_scraping(
    *,
    restaurant_id: str,
    db_path: str,
    mona_db_path: str,
) -> list[dict[str, Any]]:
    """Scrape the OpenRice partner dashboard as a fallback.

    This is intentionally conservative — it looks for a predictable table
    structure in the partner management page and extracts only the fields
    we need.
    """
    import httpx

    url = f"https://www.openrice.com/partner/manage/{restaurant_id}/bookings"
    created: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:
        logger.error("OpenRice scraping failed: %s", exc)
        return created

    rows = _parse_booking_rows(html)
    for row in rows:
        ref = row.get("channel_ref", "")
        if _already_imported(db_path, channel_ref=ref):
            continue

        booking = _import_booking(
            db_path=db_path,
            mona_db_path=mona_db_path,
            guest_name=row.get("guest_name", "OpenRice Guest"),
            guest_phone=row.get("guest_phone", ""),
            party_size=row.get("party_size", 2),
            booking_date=row.get("booking_date", ""),
            booking_time=row.get("booking_time", "19:00"),
            channel_ref=ref,
            special_requests=row.get("special_requests", ""),
        )
        created.append(booking)

    return created


def _parse_booking_rows(html: str) -> list[dict[str, Any]]:
    """Extract booking rows from the OpenRice partner dashboard HTML.

    Looks for table rows with data attributes that the partner page renders.
    Returns a list of dicts with the standard booking fields.
    """
    rows: list[dict[str, Any]] = []

    row_pattern = re.compile(
        r'data-booking-ref="(?P<ref>[^"]+)"'
        r'.*?data-guest="(?P<guest>[^"]*)"'
        r'.*?data-phone="(?P<phone>[^"]*)"'
        r'.*?data-pax="(?P<pax>\d+)"'
        r'.*?data-date="(?P<date>[^"]*)"'
        r'.*?data-time="(?P<time>[^"]*)"',
        re.DOTALL,
    )

    for m in row_pattern.finditer(html):
        rows.append({
            "channel_ref": m.group("ref"),
            "guest_name": m.group("guest"),
            "guest_phone": m.group("phone"),
            "party_size": int(m.group("pax")),
            "booking_date": m.group("date"),
            "booking_time": m.group("time"),
            "special_requests": "",
        })

    return rows


def _already_imported(db_path: str, *, channel_ref: str) -> bool:
    """Check whether a booking with this OpenRice ref already exists."""
    if not channel_ref:
        return False
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM bookings WHERE channel='openrice' AND channel_ref=? LIMIT 1",
            (channel_ref,),
        ).fetchone()
    return row is not None


def _import_booking(
    *,
    db_path: str,
    mona_db_path: str,
    guest_name: str,
    guest_phone: str,
    party_size: int,
    booking_date: str,
    booking_time: str,
    channel_ref: str,
    special_requests: str,
) -> dict[str, Any]:
    """Insert an OpenRice booking into the local database."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO bookings
               (guest_name, guest_phone, party_size, booking_date, booking_time,
                channel, channel_ref, status, special_requests, language_pref)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (guest_name, guest_phone, party_size, booking_date, booking_time,
             "openrice", channel_ref, "pending", special_requests, "zh"),
        )
        booking_id = cursor.lastrowid

    emit_event(
        mona_db_path,
        event_type="action_completed",
        tool_name="table-master",
        summary=f"OpenRice booking #{booking_id} imported: {guest_name} ({party_size}pax)",
    )

    return {
        "id": booking_id,
        "guest_name": guest_name,
        "party_size": party_size,
        "booking_date": booking_date,
        "booking_time": booking_time,
        "channel": "openrice",
        "channel_ref": channel_ref,
        "status": "pending",
    }
