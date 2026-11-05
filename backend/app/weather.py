"""Optional forecast provider. Credentials are read only from process environment."""
import asyncio
import os
from datetime import date
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class ForecastDay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    minC: float = Field(ge=-90, le=65, allow_inf_nan=False)
    maxC: float = Field(ge=-90, le=65, allow_inf_nan=False)
    rainMm: float = Field(ge=0, le=3000, allow_inf_nan=False)


class Forecast(BaseModel):
    days: list[ForecastDay] = Field(min_length=1, max_length=7)
    source: str = Field(min_length=1, max_length=120)


class WeatherClient(Protocol):
    async def forecast(self, location: str, days: int) -> dict: ...


class HttpWeatherClient:
    async def forecast(self, location: str, days: int) -> dict:
        import httpx

        key = os.environ.get("WEATHER_API_KEY", "").strip()
        if not key:
            raise ValueError("weather_unconfigured")
        # Fixed HTTPS destination; user inputs cannot select an arbitrary endpoint.
        async with httpx.AsyncClient(timeout=3, follow_redirects=False) as client:
            response = await client.get("https://api.weatherapi.com/v1/forecast.json", params={
                "key": key, "q": location, "days": days, "aqi": "no", "alerts": "no"})
            response.raise_for_status()
            data = response.json()
        return {"source": "날씨 제공 서비스", "days": [
            {"date": item["date"], "minC": item["day"]["mintemp_c"],
             "maxC": item["day"]["maxtemp_c"], "rainMm": item["day"]["totalprecip_mm"]}
            for item in data["forecast"]["forecastday"]]}


class WeatherService:
    def __init__(self, client: WeatherClient | None = None, timeout: float = 3):
        self.client = client
        self.timeout = timeout
        if self.client is None and os.environ.get("WEATHER_API_KEY", "").strip():
            self.client = HttpWeatherClient()

    async def get(self, location: str, days: int = 3) -> dict:
        if not isinstance(location, str) or not 1 <= len(location.strip()) <= 80:
            raise ValueError("invalid_location")
        if type(days) is not int or not 1 <= days <= 7:
            raise ValueError("invalid_days")
        missing = {"available": False, "summary": "날씨 정보 없음", "days": [], "source": None}
        if self.client is None:
            return missing
        try:
            async with asyncio.timeout(self.timeout):
                raw = await self.client.forecast(location, days)
                forecast = Forecast.model_validate(raw)
                if len(forecast.days) > days or any(d.minC > d.maxC for d in forecast.days):
                    return missing
                # Only numeric, validated fields enter the summary; no provider prose is echoed.
                summary = " / ".join(
                    f"{d.date.isoformat()} 최저 {d.minC:g}℃ · 최고 {d.maxC:g}℃ · 예상 강수 {d.rainMm:g}mm"
                    for d in forecast.days)
                return {"available": True, "summary": summary,
                        "days": [d.model_dump(mode="json") for d in forecast.days],
                        "source": "예보 제공 자료 (현장 측정 아님)"}
        except Exception:
            # Do not log URLs, keys, provider exceptions, or user location.
            return missing
