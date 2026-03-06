"""Hong Kong geographic / address data client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibe_coder.hk_dev_kit.connectors.govhk.open_data_client import GovHKClient


@dataclass
class HKDistrict:
    code: str
    name_en: str
    name_zh: str
    territory: str  # HK Island / Kowloon / New Territories


@dataclass
class GeoAddress:
    address_en: str
    address_zh: str
    latitude: float
    longitude: float
    district_en: str = ""
    district_zh: str = ""
    building_name: str = ""


DISTRICTS: list[HKDistrict] = [
    HKDistrict("CW", "Central and Western", "中西區", "Hong Kong Island"),
    HKDistrict("EA", "Eastern", "東區", "Hong Kong Island"),
    HKDistrict("SO", "Southern", "南區", "Hong Kong Island"),
    HKDistrict("WC", "Wan Chai", "灣仔區", "Hong Kong Island"),
    HKDistrict("KC", "Kowloon City", "九龍城區", "Kowloon"),
    HKDistrict("KT", "Kwun Tong", "觀塘區", "Kowloon"),
    HKDistrict("SSP", "Sham Shui Po", "深水埗區", "Kowloon"),
    HKDistrict("WTS", "Wong Tai Sin", "黃大仙區", "Kowloon"),
    HKDistrict("YTM", "Yau Tsim Mong", "油尖旺區", "Kowloon"),
    HKDistrict("IS", "Islands", "離島區", "New Territories"),
    HKDistrict("KI", "Kwai Tsing", "葵青區", "New Territories"),
    HKDistrict("NO", "North", "北區", "New Territories"),
    HKDistrict("SK", "Sai Kung", "西貢區", "New Territories"),
    HKDistrict("ST", "Sha Tin", "沙田區", "New Territories"),
    HKDistrict("TP", "Tai Po", "大埔區", "New Territories"),
    HKDistrict("TW", "Tsuen Wan", "荃灣區", "New Territories"),
    HKDistrict("TM", "Tuen Mun", "屯門區", "New Territories"),
    HKDistrict("YL", "Yuen Long", "元朗區", "New Territories"),
]


class HKGeoClient(GovHKClient):
    """Client for HK geographic and address data."""

    GEODATA_RESOURCE = "action/datastore_search"
    ALS_BASE = "https://www.als.ogcio.gov.hk/lookup"

    def get_districts(self, territory: str | None = None) -> list[HKDistrict]:
        """Return the 18 districts of Hong Kong, optionally filtered by territory."""
        if territory:
            return [d for d in DISTRICTS if d.territory.lower() == territory.lower()]
        return list(DISTRICTS)

    async def search_address(self, query: str, limit: int = 10) -> list[GeoAddress]:
        """Search for addresses using the OGCIO Address Lookup Service."""
        import httpx

        cache_key = self._cache_key(self.ALS_BASE, {"q": query, "n": str(limit)})
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.ALS_BASE,
                params={"q": query, "n": limit},
                headers={"Accept": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()

        results: list[GeoAddress] = []
        for item in data.get("SuggestedAddress", []):
            addr = item.get("Address", {})
            premises = addr.get("PremisesAddress", {})
            geo_addr = premises.get("GeospatialInformation", {})

            eng_addr = premises.get("EngPremisesAddress", {})
            chi_addr = premises.get("ChiPremisesAddress", {})

            eng_parts = []
            for key in ("BuildingName", "EstateName", "StreetName"):
                val = eng_addr.get(key, "")
                if val:
                    eng_parts.append(val)
            eng_text = ", ".join(eng_parts) if eng_parts else query

            chi_parts = []
            for key in ("BuildingName", "EstateName", "StreetName"):
                val = chi_addr.get(key, "")
                if val:
                    chi_parts.append(val)
            chi_text = "".join(chi_parts) if chi_parts else ""

            results.append(GeoAddress(
                address_en=eng_text,
                address_zh=chi_text,
                latitude=float(geo_addr.get("Latitude", 0)),
                longitude=float(geo_addr.get("Longitude", 0)),
                district_en=eng_addr.get("EngDistrict", {}).get("DcDistrict", ""),
                district_zh=chi_addr.get("ChiDistrict", {}).get("DcDistrict", ""),
                building_name=eng_addr.get("BuildingName", ""),
            ))

        self._set_cached(cache_key, results)
        return results

    async def reverse_geocode(self, lat: float, lng: float) -> GeoAddress | None:
        """Reverse-geocode coordinates to the nearest HK address."""
        results = await self.search_address(f"{lat},{lng}", limit=1)
        return results[0] if results else None
