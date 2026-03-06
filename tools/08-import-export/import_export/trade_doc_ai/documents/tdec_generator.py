"""Trade Declaration (TDEC) generator for Hong Kong Customs & Excise."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger("openclaw.trade-doc-ai.tdec")

DECLARATION_TYPES = {"import", "export", "re_export"}
TRANSPORT_MODES = {"sea", "air", "land", "rail", "post", "multimodal"}
FILING_DEADLINE_DAYS = 14


class TDECGenerator:
    """Generate TDEC (Trade Declaration) form data for electronic filing.

    Hong Kong requires import/export declarations to be filed within 14 days
    of the import/export date via Tradelink or BECS.
    """

    def generate(self, declaration_data: dict) -> dict:
        """Create a complete TDEC form payload from raw declaration data.

        Required fields in declaration_data:
          - declaration_type: import | export | re_export
          - shipper, consignee
          - items: list of item dicts with hs_code, description, quantity, value, etc.

        Returns the fully populated form dict ready for filing.
        """
        decl_type = declaration_data.get("declaration_type", "import")
        if decl_type not in DECLARATION_TYPES:
            raise ValueError(f"Invalid declaration_type: {decl_type}. Must be one of {DECLARATION_TYPES}")

        declaration_date = declaration_data.get("declaration_date")
        if isinstance(declaration_date, str):
            declaration_date = date.fromisoformat(declaration_date)
        elif declaration_date is None:
            declaration_date = date.today()

        items = declaration_data.get("items", [])
        processed_items = [self._process_item(item, i + 1) for i, item in enumerate(items)]

        total_value = sum(it.get("value", 0) for it in processed_items)
        total_quantity = sum(it.get("quantity", 0) for it in processed_items)

        form: dict[str, Any] = {
            "form_type": self._form_type_code(decl_type),
            "declaration_type": decl_type,
            "declaration_date": declaration_date.isoformat(),
            "filing_deadline": self.calculate_deadline(declaration_date).isoformat(),
            "shipper": {
                "name": declaration_data.get("shipper", ""),
                "address": declaration_data.get("shipper_address", ""),
                "br_number": declaration_data.get("shipper_br", ""),
            },
            "consignee": {
                "name": declaration_data.get("consignee", ""),
                "address": declaration_data.get("consignee_address", ""),
            },
            "transport": {
                "mode": declaration_data.get("transport_mode", "sea"),
                "vessel_flight": declaration_data.get("vessel_flight", ""),
                "bill_of_lading": declaration_data.get("bill_of_lading", ""),
            },
            "country_of_origin": declaration_data.get("country_of_origin", ""),
            "country_of_destination": declaration_data.get("country_of_destination", ""),
            "currency": declaration_data.get("currency", "HKD"),
            "total_value": total_value,
            "total_quantity": total_quantity,
            "items": processed_items,
            "item_count": len(processed_items),
        }

        if decl_type == "re_export":
            form["linked_import_reference"] = declaration_data.get("linked_import_reference", "")
            form["original_import_date"] = declaration_data.get("original_import_date", "")

        if decl_type == "import":
            form["dutiable_commodities"] = self._check_dutiable(processed_items)

        return form

    def calculate_deadline(self, declaration_date: date) -> date:
        """Filing deadline is 14 calendar days from the declaration date."""
        if isinstance(declaration_date, str):
            declaration_date = date.fromisoformat(declaration_date)
        return declaration_date + timedelta(days=FILING_DEADLINE_DAYS)

    @staticmethod
    def _form_type_code(decl_type: str) -> str:
        return {
            "import": "TDEC-I",
            "export": "TDEC-E",
            "re_export": "TDEC-RE",
        }.get(decl_type, "TDEC-I")

    @staticmethod
    def _process_item(item: dict, line_number: int) -> dict:
        """Normalise and validate a single line item."""
        return {
            "line_number": line_number,
            "hs_code": (item.get("hs_code") or "").replace(".", "").strip(),
            "description": item.get("description", ""),
            "quantity": float(item.get("quantity", 0)),
            "unit": item.get("unit", "pieces"),
            "value": float(item.get("value", 0)),
            "currency": item.get("currency", "HKD"),
            "country_of_origin": item.get("country_of_origin", ""),
            "weight_kg": float(item.get("weight_kg", 0)),
        }

    @staticmethod
    def _check_dutiable(items: list[dict]) -> list[dict]:
        """Flag items in the four HK dutiable commodity categories."""
        dutiable_prefixes = {
            "2203": "Beer",
            "2204": "Wine",
            "2205": "Vermouth",
            "2206": "Cider/Perry",
            "2207": "Ethyl alcohol",
            "2208": "Spirits",
            "2402": "Tobacco",
            "2710": "Hydrocarbon oil",
            "2711": "Methyl alcohol",
        }
        flagged = []
        for item in items:
            hs4 = (item.get("hs_code") or "")[:4]
            if hs4 in dutiable_prefixes:
                flagged.append({
                    "hs_code": item["hs_code"],
                    "category": dutiable_prefixes[hs4],
                    "description": item["description"],
                    "value": item["value"],
                })
        return flagged
