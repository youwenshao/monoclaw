"""Certificate of Origin (CO) generator supporting general, CEPA, and ASEAN-HK FTA."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

logger = logging.getLogger("openclaw.trade-doc-ai.co")

CO_TYPES = {"general", "cepa", "asean_hk", "other_preferential"}

CEPA_QUALIFYING_RULES = {
    "substantial_transformation": (
        "Product must have undergone substantial transformation in Hong Kong. "
        "The CCC (Change in Customs Classification) or RVC (Regional Value Content >= 30%) "
        "rule applies."
    ),
    "hk_origin_criteria": (
        "The product is wholly obtained or produced in Hong Kong, "
        "or last substantial manufacturing process was performed in Hong Kong."
    ),
}

ASEAN_HK_ROO = {
    "rvc_threshold": 40,
    "description": (
        "Under the ASEAN-HK FTA, the Regional Value Content must be at least 40%, "
        "OR the product must satisfy the applicable Change in Tariff Classification rule."
    ),
}


class COGenerator:
    """Generate Certificate of Origin applications for Hong Kong exports."""

    def generate(self, co_data: dict) -> dict:
        """Create a CO application with all required fields.

        Required keys:
          - co_type: general | cepa | asean_hk | other_preferential
          - exporter (dict: name, address, br_number)
          - consignee (dict: name, address, country)
          - products (list of dicts: description, hs_code, quantity, value, origin_criterion)
          - declaration_id (int, optional link to trade_declarations)

        Returns the complete CO application dict.
        """
        co_type = co_data.get("co_type", "general")
        if co_type not in CO_TYPES:
            raise ValueError(f"Invalid co_type: {co_type}. Must be one of {CO_TYPES}")

        products = [self._process_product(p) for p in co_data.get("products", [])]
        total_value = sum(p["value"] for p in products)

        application: dict[str, Any] = {
            "co_type": co_type,
            "application_date": date.today().isoformat(),
            "issuing_body": self._issuing_body(co_type),
            "exporter": {
                "name": co_data.get("exporter", {}).get("name", ""),
                "address": co_data.get("exporter", {}).get("address", ""),
                "br_number": co_data.get("exporter", {}).get("br_number", ""),
            },
            "consignee": {
                "name": co_data.get("consignee", {}).get("name", ""),
                "address": co_data.get("consignee", {}).get("address", ""),
                "country": co_data.get("consignee", {}).get("country", ""),
            },
            "products": products,
            "total_value": total_value,
            "currency": co_data.get("currency", "HKD"),
            "transport": {
                "mode": co_data.get("transport_mode", "sea"),
                "vessel_flight": co_data.get("vessel_flight", ""),
                "departure_date": co_data.get("departure_date", ""),
                "port_of_loading": co_data.get("port_of_loading", "Hong Kong"),
                "port_of_discharge": co_data.get("port_of_discharge", ""),
            },
            "declaration_id": co_data.get("declaration_id"),
        }

        if co_type == "cepa":
            application["cepa_details"] = {
                "factory_registration": co_data.get("factory_registration", ""),
                "qualifying_rule": CEPA_QUALIFYING_RULES["substantial_transformation"],
                "hk_value_added_pct": co_data.get("hk_value_added_pct", 0),
            }
        elif co_type == "asean_hk":
            application["fta_details"] = {
                "rvc_threshold": ASEAN_HK_ROO["rvc_threshold"],
                "description": ASEAN_HK_ROO["description"],
                "declared_rvc_pct": co_data.get("declared_rvc_pct", 0),
            }

        return application

    def check_cepa_eligibility(self, product: dict) -> bool:
        """Check whether a product likely qualifies under CEPA rules of origin.

        A product qualifies if:
        1. It was substantially transformed in HK (origin_criterion == "substantial_transformation"), OR
        2. The declared HK value-added percentage >= 30%.
        """
        criterion = product.get("origin_criterion", "")
        if criterion in ("substantial_transformation", "wholly_obtained"):
            return True

        hk_value_pct = float(product.get("hk_value_added_pct", 0))
        if hk_value_pct >= 30.0:
            return True

        return False

    @staticmethod
    def _issuing_body(co_type: str) -> str:
        return {
            "general": "Hong Kong General Chamber of Commerce / TID",
            "cepa": "Trade and Industry Department (TID)",
            "asean_hk": "Trade and Industry Department (TID)",
            "other_preferential": "Relevant issuing authority",
        }.get(co_type, "TID")

    @staticmethod
    def _process_product(product: dict) -> dict:
        return {
            "description": product.get("description", ""),
            "hs_code": product.get("hs_code", ""),
            "quantity": float(product.get("quantity", 0)),
            "unit": product.get("unit", "pieces"),
            "value": float(product.get("value", 0)),
            "country_of_origin": product.get("country_of_origin", "Hong Kong"),
            "origin_criterion": product.get("origin_criterion", ""),
        }
