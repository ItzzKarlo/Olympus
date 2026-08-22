from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


WeatherCondition = Literal[
    "clear", "mostly_clear", "partly_cloudy", "cloudy", "fog", "drizzle",
    "rain", "heavy_rain", "snow", "thunderstorm", "unknown",
]


class WeatherLocation(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str
    name: str | None = None


class CurrentWeather(BaseModel):
    temperature_c: float | None = None
    apparent_temperature_c: float | None = None
    condition: WeatherCondition = "unknown"
    precipitation_probability: int | None = Field(default=None, ge=0, le=100)
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    is_day: bool | None = None


class DailyWeather(BaseModel):
    date: date
    high_c: float | None = None
    low_c: float | None = None
    condition: WeatherCondition = "unknown"
    sunrise: datetime | None = None
    sunset: datetime | None = None
    precipitation_probability_max: int | None = Field(default=None, ge=0, le=100)


class WeatherState(BaseModel):
    available: bool = True
    stale: bool = False
    observed_at: datetime
    location: WeatherLocation
    current: CurrentWeather | None = None
    today: DailyWeather | None = None
    tomorrow: DailyWeather | None = None
