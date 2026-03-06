"""Phone / walk-in entry — Pydantic models and helpers for manual bookings."""

from __future__ import annotations

import re
from datetime import date, time
from typing import Any

from pydantic import BaseModel, field_validator

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


class ManualBookingRequest(BaseModel):
    """Request body for creating a booking via phone or walk-in."""

    guest_name: str
    guest_phone: str
    party_size: int
    booking_date: str
    booking_time: str
    channel: str = "phone"
    special_requests: str = ""
    language_pref: str = "zh"
    table_id: int | None = None

    @field_validator("guest_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if v and not HK_PHONE_RE.match(v):
            raise ValueError("Phone must be a valid HK number: +852XXXXXXXX")
        return v

    @field_validator("party_size")
    @classmethod
    def validate_party(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("Party size must be between 1 and 50")
        return v

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        allowed = {"phone", "walk_in", "walkin", "walk-in"}
        if v.lower() not in allowed:
            raise ValueError(f"Channel must be one of: {', '.join(sorted(allowed))}")
        return v.lower().replace("-", "_").replace("walkin", "walk_in")


class ManualBookingResponse(BaseModel):
    id: int
    guest_name: str
    party_size: int
    booking_date: str
    booking_time: str
    table_id: int | None
    channel: str
    status: str


def create_manual_booking(
    body: ManualBookingRequest,
    *,
    db_path: str,
    mona_db_path: str,
) -> ManualBookingResponse:
    """Insert a phone / walk-in booking and emit an activity event."""
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO bookings
               (guest_name, guest_phone, party_size, booking_date, booking_time,
                table_id, channel, status, special_requests, language_pref)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                body.guest_name,
                body.guest_phone,
                body.party_size,
                body.booking_date,
                body.booking_time,
                body.table_id,
                body.channel,
                "pending",
                body.special_requests,
                body.language_pref,
            ),
        )
        booking_id = cursor.lastrowid

    emit_event(
        mona_db_path,
        event_type="action_completed",
        tool_name="table-master",
        summary=f"Manual booking #{booking_id}: {body.guest_name} ({body.party_size}pax) via {body.channel}",
    )

    return ManualBookingResponse(
        id=booking_id,
        guest_name=body.guest_name,
        party_size=body.party_size,
        booking_date=body.booking_date,
        booking_time=body.booking_time,
        table_id=body.table_id,
        channel=body.channel,
        status="pending",
    )
