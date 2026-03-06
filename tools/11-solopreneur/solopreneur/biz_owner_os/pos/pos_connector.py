"""Multi-provider POS connector for syncing sales data.

Supports iCHEF, Lightspeed, Square, and CSV import.  Each connector
normalises transactions into a common dict schema before persisting.
"""

from __future__ import annotations

import csv
import io
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any


class POSConnector(ABC):
    """Base class for POS system integrations."""

    provider: str = "generic"

    def __init__(self, api_key: str = "", api_secret: str = "") -> None:
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    async def sync_sales(self, since_date: date | None = None) -> list[dict[str, Any]]:
        """Fetch sales since *since_date* and return normalised dicts.

        Each dict must have at minimum:
        ``pos_transaction_id``, ``sale_date``, ``total_amount``,
        ``payment_method``, ``items`` (JSON string), ``customer_phone``.
        """
        ...

    def _normalise(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Provide sensible defaults for missing fields."""
        return {
            "pos_transaction_id": raw.get("pos_transaction_id", ""),
            "sale_date": raw.get("sale_date", datetime.now().isoformat()),
            "total_amount": float(raw.get("total_amount", 0)),
            "payment_method": raw.get("payment_method", "other"),
            "items": raw.get("items", "[]"),
            "customer_phone": raw.get("customer_phone", ""),
            "pos_source": self.provider,
        }


class ICHEFConnector(POSConnector):
    """Connector for the iCHEF POS system (popular in HK F&B)."""

    provider = "ichef"

    async def sync_sales(self, since_date: date | None = None) -> list[dict[str, Any]]:
        # In production this would call the iCHEF API; stubbed for now.
        return []


class LightspeedConnector(POSConnector):
    """Connector for Lightspeed Retail / Restaurant."""

    provider = "lightspeed"

    async def sync_sales(self, since_date: date | None = None) -> list[dict[str, Any]]:
        return []


class SquareConnector(POSConnector):
    """Connector for Square POS."""

    provider = "square"

    async def sync_sales(self, since_date: date | None = None) -> list[dict[str, Any]]:
        return []


class CSVImporter(POSConnector):
    """Import sales from a CSV file/string.

    Expected columns: ``transaction_id, date, amount, payment_method,
    items, customer_phone``.
    """

    provider = "csv"

    def __init__(self, csv_data: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.csv_data = csv_data

    async def sync_sales(self, since_date: date | None = None) -> list[dict[str, Any]]:
        if not self.csv_data:
            return []

        reader = csv.DictReader(io.StringIO(self.csv_data))
        results: list[dict[str, Any]] = []
        for row in reader:
            sale_date_str = row.get("date", "")
            if since_date and sale_date_str:
                try:
                    if datetime.fromisoformat(sale_date_str).date() < since_date:
                        continue
                except ValueError:
                    pass

            results.append(self._normalise({
                "pos_transaction_id": row.get("transaction_id", ""),
                "sale_date": sale_date_str or datetime.now().isoformat(),
                "total_amount": row.get("amount", 0),
                "payment_method": row.get("payment_method", "other"),
                "items": row.get("items", "[]"),
                "customer_phone": row.get("customer_phone", ""),
            }))
        return results


_PROVIDERS: dict[str, type[POSConnector]] = {
    "ichef": ICHEFConnector,
    "lightspeed": LightspeedConnector,
    "square": SquareConnector,
    "csv": CSVImporter,
}


def create_connector(
    provider: str,
    api_key: str = "",
    api_secret: str = "",
) -> POSConnector:
    """Factory for POS connectors.

    Raises ``ValueError`` for unknown providers.
    """
    cls = _PROVIDERS.get(provider.lower())
    if cls is None:
        raise ValueError(
            f"Unknown POS provider '{provider}'. "
            f"Supported: {', '.join(_PROVIDERS)}"
        )
    return cls(api_key=api_key, api_secret=api_secret)
