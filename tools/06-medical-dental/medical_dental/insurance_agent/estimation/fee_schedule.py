"""Clinic fee schedule management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.medical-dental.insurance.fees")

DEFAULT_HK_FEES: dict[str, dict[str, Any]] = {
    "gp_consultation": {
        "description": "General practitioner consultation",
        "min_fee": 300,
        "max_fee": 800,
        "default_fee": 500,
        "currency": "HKD",
    },
    "specialist": {
        "description": "Specialist consultation",
        "min_fee": 800,
        "max_fee": 2500,
        "default_fee": 1200,
        "currency": "HKD",
    },
    "dental_checkup": {
        "description": "Dental check-up and cleaning",
        "min_fee": 500,
        "max_fee": 1500,
        "default_fee": 800,
        "currency": "HKD",
    },
    "dental_basic": {
        "description": "Basic dental treatment (filling, extraction)",
        "min_fee": 600,
        "max_fee": 2000,
        "default_fee": 1000,
        "currency": "HKD",
    },
    "dental_major": {
        "description": "Major dental work (crown, root canal)",
        "min_fee": 3000,
        "max_fee": 15000,
        "default_fee": 6000,
        "currency": "HKD",
    },
    "x_ray": {
        "description": "X-ray imaging",
        "min_fee": 200,
        "max_fee": 800,
        "default_fee": 400,
        "currency": "HKD",
    },
    "blood_test": {
        "description": "Standard blood panel",
        "min_fee": 300,
        "max_fee": 1200,
        "default_fee": 600,
        "currency": "HKD",
    },
    "follow_up": {
        "description": "Follow-up consultation",
        "min_fee": 200,
        "max_fee": 600,
        "default_fee": 350,
        "currency": "HKD",
    },
    "physiotherapy": {
        "description": "Physiotherapy session",
        "min_fee": 400,
        "max_fee": 1200,
        "default_fee": 700,
        "currency": "HKD",
    },
}


class FeeSchedule:
    """Manage clinic fee schedules with CRUD operations and JSON persistence."""

    def __init__(self, fees: dict[str, dict[str, Any]] | None = None) -> None:
        self._fees: dict[str, dict[str, Any]] = {}
        if fees:
            self._fees.update(fees)
        else:
            self._fees.update({k: dict(v) for k, v in DEFAULT_HK_FEES.items()})

    def get_fee(self, procedure: str) -> dict[str, Any] | None:
        """Return fee details for a procedure, or None if not found."""
        entry = self._fees.get(procedure)
        if entry is None:
            return None
        return {"procedure": procedure, **entry}

    def get_default_amount(self, procedure: str) -> float:
        """Return the default fee amount for a procedure, or 0 if unknown."""
        entry = self._fees.get(procedure)
        if entry is None:
            return 0.0
        return float(entry.get("default_fee", 0))

    def update_fee(self, procedure: str, amount: float, *, description: str | None = None) -> dict[str, Any]:
        """Update or create a fee entry. Returns the updated entry."""
        if procedure in self._fees:
            self._fees[procedure]["default_fee"] = amount
            if description is not None:
                self._fees[procedure]["description"] = description
        else:
            self._fees[procedure] = {
                "description": description or procedure.replace("_", " ").title(),
                "min_fee": amount,
                "max_fee": amount,
                "default_fee": amount,
                "currency": "HKD",
            }
        logger.info("Updated fee for %s: HK$%.0f", procedure, amount)
        return {"procedure": procedure, **self._fees[procedure]}

    def delete_fee(self, procedure: str) -> bool:
        """Remove a procedure from the schedule. Returns True if it existed."""
        return self._fees.pop(procedure, None) is not None

    def list_fees(self) -> list[dict[str, Any]]:
        """Return all fee entries as a list."""
        return [{"procedure": k, **v} for k, v in sorted(self._fees.items())]

    def load_from_json(self, path: str | Path) -> None:
        """Load fee schedule from a JSON file, merging into current state."""
        p = Path(path)
        if not p.exists():
            logger.warning("Fee schedule file not found: %s", p)
            return
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            self._fees.update(data)
            logger.info("Loaded %d fee entries from %s", len(data), p)

    def save_to_json(self, path: str | Path) -> None:
        """Persist current fee schedule to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump(self._fees, f, indent=2, ensure_ascii=False)
        logger.info("Saved %d fee entries to %s", len(self._fees), p)
