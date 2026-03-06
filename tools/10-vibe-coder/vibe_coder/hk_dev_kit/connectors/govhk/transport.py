"""Hong Kong transport data client (MTR, bus routes)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibe_coder.hk_dev_kit.connectors.govhk.open_data_client import GovHKClient


@dataclass
class MTRLine:
    line_code: str
    name_en: str
    name_zh: str
    stations: list[str] = field(default_factory=list)
    color: str = ""


@dataclass
class BusRoute:
    route: str
    company: str
    origin_en: str
    origin_zh: str
    dest_en: str
    dest_zh: str
    service_type: str = ""


@dataclass
class BusETA:
    route: str
    stop_id: str
    eta: str
    destination_en: str
    destination_zh: str
    remarks_en: str = ""
    remarks_zh: str = ""


class HKTransportClient(GovHKClient):
    """Client for Hong Kong public transport open data."""

    MTR_LINES_RESOURCE = "action/datastore_search"
    KMB_BASE = "https://data.etabus.gov.hk/v1/transport/kmb"

    async def get_mtr_lines(self) -> list[MTRLine]:
        """Return available MTR lines from data.gov.hk."""
        try:
            data = await self.get_data(
                self.MTR_LINES_RESOURCE,
                {"resource_id": "0b887e06-e32d-4a80-af7d-e3c5a0572b93", "limit": 100},
            )
            records = data.get("result", {}).get("records", [])
        except Exception:
            return self._fallback_mtr_lines()

        lines: list[MTRLine] = []
        seen: set[str] = set()
        for rec in records:
            code = rec.get("Line Code", "")
            if code and code not in seen:
                seen.add(code)
                lines.append(MTRLine(
                    line_code=code,
                    name_en=rec.get("English Name", code),
                    name_zh=rec.get("Chinese Name", code),
                    color=rec.get("Colour Code", ""),
                ))
        return lines

    async def get_bus_routes(self, company: str = "KMB") -> list[BusRoute]:
        """Fetch bus routes for a given company (defaults to KMB)."""
        if company.upper() == "KMB":
            return await self._get_kmb_routes()

        data = await self.get_data(
            self.MTR_LINES_RESOURCE,
            {"resource_id": "1b74e2a6-1b5d-45b9-96e5-9f9db9972b6f", "limit": 500},
        )
        records = data.get("result", {}).get("records", [])
        return [
            BusRoute(
                route=r.get("route", ""),
                company=r.get("co", company),
                origin_en=r.get("orig_en", ""),
                origin_zh=r.get("orig_tc", ""),
                dest_en=r.get("dest_en", ""),
                dest_zh=r.get("dest_tc", ""),
            )
            for r in records
        ]

    async def get_bus_eta(self, stop_id: str, route: str) -> list[BusETA]:
        """Fetch estimated arrival times for a bus stop + route (KMB)."""
        url = f"{self.KMB_BASE}/eta/{stop_id}/{route}/1"
        cache_key = self._cache_key(url, None)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()

        etas = [
            BusETA(
                route=item.get("route", route),
                stop_id=stop_id,
                eta=item.get("eta", ""),
                destination_en=item.get("dest_en", ""),
                destination_zh=item.get("dest_tc", ""),
                remarks_en=item.get("rmk_en", ""),
                remarks_zh=item.get("rmk_tc", ""),
            )
            for item in data.get("data", [])
            if item.get("eta")
        ]
        self._set_cached(cache_key, etas)
        return etas

    async def _get_kmb_routes(self) -> list[BusRoute]:
        url = f"{self.KMB_BASE}/route/"
        cache_key = self._cache_key(url, None)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

        routes = [
            BusRoute(
                route=r.get("route", ""),
                company="KMB",
                origin_en=r.get("orig_en", ""),
                origin_zh=r.get("orig_tc", ""),
                dest_en=r.get("dest_en", ""),
                dest_zh=r.get("dest_tc", ""),
                service_type=r.get("service_type", ""),
            )
            for r in data.get("data", [])
        ]
        self._set_cached(cache_key, routes)
        return routes

    @staticmethod
    def _fallback_mtr_lines() -> list[MTRLine]:
        """Hard-coded fallback when the data.gov.hk API is unavailable."""
        return [
            MTRLine("AEL", "Airport Express", "機場快綫", color="#1C7670"),
            MTRLine("TCL", "Tung Chung Line", "東涌綫", color="#F7943E"),
            MTRLine("TKL", "Tseung Kwan O Line", "將軍澳綫", color="#7D499D"),
            MTRLine("TML", "Tuen Ma Line", "屯馬綫", color="#9A3B26"),
            MTRLine("EAL", "East Rail Line", "東鐵綫", color="#5EB6E4"),
            MTRLine("SIL", "South Island Line", "南港島綫", color="#BAC429"),
            MTRLine("TWL", "Tsuen Wan Line", "荃灣綫", color="#E2231A"),
            MTRLine("ISL", "Island Line", "港島綫", color="#0075C2"),
            MTRLine("KTL", "Kwun Tong Line", "觀塘綫", color="#1A9431"),
        ]
