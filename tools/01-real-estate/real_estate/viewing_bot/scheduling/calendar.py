"""Apple Calendar (EventKit) integration for viewing events.

Uses pyobjc-framework-EventKit when available on macOS.
Gracefully returns empty results on other platforms.
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Any

logger = logging.getLogger("openclaw.viewing_bot.calendar")

_eventkit_available = False
_EKEventStore = None
_EKEvent = None
_EKSpan = None
_NSDate = None

try:
    from EventKit import (  # type: ignore[import-untyped]
        EKEventStore,
        EKEvent,
        EKEntityTypeEvent,
        EKSpanThisEvent,
        EKAuthorizationStatusAuthorized,
    )
    from Foundation import NSDate  # type: ignore[import-untyped]
    _eventkit_available = True
    _EKEventStore = EKEventStore
    _EKEvent = EKEvent
    _EKSpan = EKSpanThisEvent
    _NSDate = NSDate
except ImportError:
    logger.info("EventKit not available — calendar integration disabled")


def _nsdate_from_datetime(dt: datetime) -> Any:
    """Convert a Python datetime to an NSDate."""
    if _NSDate is None:
        return None
    epoch = dt.timestamp()
    return _NSDate.dateWithTimeIntervalSince1970_(epoch)


def _datetime_from_nsdate(nsdate: Any) -> datetime:
    """Convert an NSDate to a Python datetime."""
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970())


def _get_store() -> Any | None:
    """Get an authorised EKEventStore, or None."""
    if not _eventkit_available or _EKEventStore is None:
        return None
    store = _EKEventStore.alloc().init()
    return store


def create_calendar_event(
    title: str,
    start: datetime,
    end: datetime,
    location: str = "",
    notes: str = "",
) -> str | None:
    """Create a calendar event via EventKit.

    Returns the event identifier string, or None if EventKit is unavailable.
    """
    store = _get_store()
    if store is None or _EKEvent is None:
        logger.debug("Skipping calendar event creation — EventKit unavailable")
        return None

    try:
        event = _EKEvent.eventWithEventStore_(store)
        event.setTitle_(title)
        event.setStartDate_(_nsdate_from_datetime(start))
        event.setEndDate_(_nsdate_from_datetime(end))
        if location:
            event.setLocation_(location)
        if notes:
            event.setNotes_(notes)
        event.setCalendar_(store.defaultCalendarForNewEvents())

        success, error = store.saveEvent_span_error_(event, _EKSpan, None)
        if success:
            logger.info("Calendar event created: %s", event.eventIdentifier())
            return event.eventIdentifier()
        else:
            logger.warning("Failed to save calendar event: %s", error)
            return None
    except Exception as exc:
        logger.warning("Calendar event creation failed: %s", exc)
        return None


def get_events_for_date(target_date: date) -> list[dict[str, Any]]:
    """Retrieve calendar events for a given date.

    Returns a list of dicts with: title, start, end, location, notes.
    Returns an empty list if EventKit is unavailable.
    """
    store = _get_store()
    if store is None:
        return []

    try:
        start_dt = datetime.combine(target_date, datetime.min.time())
        end_dt = datetime.combine(target_date, datetime.max.time())

        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            _nsdate_from_datetime(start_dt),
            _nsdate_from_datetime(end_dt),
            None,
        )
        events = store.eventsMatchingPredicate_(predicate)
        if not events:
            return []

        result: list[dict[str, Any]] = []
        for ev in events:
            result.append({
                "title": ev.title() or "",
                "start": _datetime_from_nsdate(ev.startDate()).isoformat(),
                "end": _datetime_from_nsdate(ev.endDate()).isoformat(),
                "location": ev.location() or "",
                "notes": ev.notes() or "",
            })
        return result
    except Exception as exc:
        logger.warning("Failed to read calendar events: %s", exc)
        return []
