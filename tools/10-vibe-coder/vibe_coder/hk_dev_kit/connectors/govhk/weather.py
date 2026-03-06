"""Hong Kong Observatory weather API client with bilingual support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vibe_coder.hk_dev_kit.connectors.govhk.open_data_client import GovHKClient


@dataclass
class WeatherData:
    temperature: float
    humidity: int
    uvindex: float | None = None
    icon: str = ""
    description_en: str = ""
    description_zh: str = ""
    update_time: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class ForecastDay:
    date: str
    week: str
    wind: str
    weather_en: str
    weather_zh: str
    temp_min: float
    temp_max: float
    humidity_min: int
    humidity_max: int
    icon: str = ""


@dataclass
class ForecastData:
    general_situation_en: str = ""
    general_situation_zh: str = ""
    days: list[ForecastDay] = field(default_factory=list)
    update_time: str = ""


@dataclass
class Warning:
    name: str
    code: str
    action_code: str = ""
    issued_at: str = ""
    description_en: str = ""
    description_zh: str = ""


class HKWeatherClient(GovHKClient):
    """Client for the HK Observatory public weather API.

    All responses are bilingual (English + Traditional Chinese) where the
    upstream API provides both languages.
    """

    async def get_current_weather(self, lang: str = "en") -> WeatherData:
        """Fetch real-time regional weather readings."""
        data_en = await self.get_weather("weather.php", {"dataType": "rhrread", "lang": "en"})
        data_zh = await self.get_weather("weather.php", {"dataType": "rhrread", "lang": "tc"})

        temp = 0.0
        humidity = 0
        for item in data_en.get("temperature", {}).get("data", []):
            if item.get("place") == "Hong Kong Observatory":
                temp = item.get("value", 0.0)
                break
        for item in data_en.get("humidity", {}).get("data", []):
            if item.get("place") == "Hong Kong Observatory":
                humidity = item.get("value", 0)
                break

        uvindex = None
        uv_data = data_en.get("uvindex", {}).get("data", [])
        if uv_data:
            uvindex = uv_data[0].get("value")

        icon_num = ""
        icons = data_en.get("icon", [])
        if icons:
            icon_num = str(icons[0])

        return WeatherData(
            temperature=temp,
            humidity=humidity,
            uvindex=uvindex,
            icon=icon_num,
            description_en=data_en.get("generalSituation", ""),
            description_zh=data_zh.get("generalSituation", ""),
            update_time=data_en.get("updateTime", ""),
            raw=data_en if lang == "en" else data_zh,
        )

    async def get_forecast(self) -> ForecastData:
        """Fetch 9-day weather forecast."""
        data_en = await self.get_weather("weather.php", {"dataType": "fnd", "lang": "en"})
        data_zh = await self.get_weather("weather.php", {"dataType": "fnd", "lang": "tc"})

        days: list[ForecastDay] = []
        for item_en, item_zh in zip(
            data_en.get("weatherForecast", []),
            data_zh.get("weatherForecast", []),
        ):
            days.append(ForecastDay(
                date=item_en.get("forecastDate", ""),
                week=item_en.get("week", ""),
                wind=item_en.get("forecastWind", ""),
                weather_en=item_en.get("forecastWeather", ""),
                weather_zh=item_zh.get("forecastWeather", ""),
                temp_min=item_en.get("forecastMintemp", {}).get("value", 0),
                temp_max=item_en.get("forecastMaxtemp", {}).get("value", 0),
                humidity_min=item_en.get("forecastMinrh", {}).get("value", 0),
                humidity_max=item_en.get("forecastMaxrh", {}).get("value", 0),
                icon=str(item_en.get("ForecastIcon", "")),
            ))

        return ForecastData(
            general_situation_en=data_en.get("generalSituation", ""),
            general_situation_zh=data_zh.get("generalSituation", ""),
            days=days,
            update_time=data_en.get("updateTime", ""),
        )

    async def get_warnings(self) -> list[Warning]:
        """Fetch active weather warnings."""
        data_en = await self.get_weather("weather.php", {"dataType": "warningInfo", "lang": "en"})
        data_zh = await self.get_weather("weather.php", {"dataType": "warningInfo", "lang": "tc"})

        warnings: list[Warning] = []
        for item_en in data_en.get("details", []):
            name = item_en.get("warningStatementCode", "")
            zh_desc = ""
            for item_zh in data_zh.get("details", []):
                if item_zh.get("warningStatementCode") == name:
                    zh_desc = item_zh.get("contents", [""])[0] if item_zh.get("contents") else ""
                    break

            warnings.append(Warning(
                name=item_en.get("subtype", name),
                code=name,
                action_code=item_en.get("actionCode", ""),
                issued_at=item_en.get("updateTime", ""),
                description_en=item_en.get("contents", [""])[0] if item_en.get("contents") else "",
                description_zh=zh_desc,
            ))

        return warnings
