from datetime import datetime, timezone
import unittest

import httpx

from olympus_core.config import WeatherSettings, parse_core_config
from olympus_core.integrations.weather import OpenMeteoApi, WeatherCollector, normalize_weather, weather_condition
from olympus_core.models.weather import WeatherState


SETTINGS = WeatherSettings(
    enabled=True,
    latitude=45.815,
    longitude=15.982,
    timezone="Europe/Zagreb",
    location_name="Home",
    poll_seconds=600,
    stale_seconds=1_800,
    unavailable_seconds=21_600,
)

PAYLOAD = {
    "current": {
        "temperature_2m": 21.4,
        "apparent_temperature": 20.8,
        "precipitation_probability": 10,
        "weather_code": 2,
        "wind_speed_10m": 8.4,
        "is_day": 1,
    },
    "daily": {
        "time": ["2026-08-22", "2026-08-23"],
        "temperature_2m_max": [24, 22],
        "temperature_2m_min": [16, 15],
        "weather_code": [2, 63],
        "sunrise": ["2026-08-22T06:03", "2026-08-23T06:04"],
        "sunset": ["2026-08-22T19:51", "2026-08-23T19:49"],
        "precipitation_probability_max": [20, 70],
    },
}


class WeatherNormalizationTests(unittest.TestCase):
    def test_normalizes_current_today_and_tomorrow(self) -> None:
        state = normalize_weather(PAYLOAD, SETTINGS, datetime(2026, 8, 22, tzinfo=timezone.utc))
        self.assertEqual(state.current.temperature_c, 21.4)
        self.assertEqual(state.current.condition, "partly_cloudy")
        self.assertEqual(state.today.high_c, 24)
        self.assertEqual(state.tomorrow.condition, "rain")
        self.assertEqual(state.today.sunrise.utcoffset().total_seconds(), 7_200)

    def test_condition_mapping_and_optional_fields(self) -> None:
        self.assertEqual(weather_condition(0), "clear")
        self.assertEqual(weather_condition(65), "heavy_rain")
        self.assertEqual(weather_condition(75), "snow")
        self.assertEqual(weather_condition(95), "thunderstorm")
        self.assertEqual(weather_condition(999), "unknown")
        state = normalize_weather(
            {"current": {"weather_code": None}, "daily": {"time": ["2026-08-22"]}},
            SETTINGS,
        )
        self.assertIsNone(state.current.temperature_c)
        self.assertIsNone(state.tomorrow)

    def test_disabled_and_unconfigured_weather_remains_optional(self) -> None:
        config = parse_core_config({"weather": {"enabled": True, "latitude": "bad"}})
        self.assertFalse(config.weather.configured)
        self.assertEqual(parse_core_config({}).timezone, "UTC")

    def test_configures_coordinates_polling_and_timezone(self) -> None:
        config = parse_core_config({
            "olympus": {"timezone": "Europe/Zagreb"},
            "weather": {"enabled": True, "latitude": 45.815, "longitude": 15.982, "poll_minutes": 12},
        })
        self.assertTrue(config.weather.configured)
        self.assertEqual(config.weather.timezone, "Europe/Zagreb")
        self.assertEqual(config.weather.poll_seconds, 720)


class WeatherApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_meteo_request_and_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.host, "api.open-meteo.com")
            self.assertEqual(request.url.params["timezone"], "Europe/Zagreb")
            return httpx.Response(200, json=PAYLOAD)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        state = await OpenMeteoApi(SETTINGS, client).fetch()
        await client.aclose()
        self.assertTrue(state.available)
        self.assertEqual(state.location.name, "Home")


class FakeWeatherGateway:
    def __init__(self, outcomes: list[WeatherState | Exception]) -> None:
        self.outcomes = outcomes

    async def fetch(self) -> WeatherState:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def aclose(self) -> None:
        return None


class WeatherCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_retains_then_stales_and_expires_recent_state(self) -> None:
        state = normalize_weather(PAYLOAD, SETTINGS)
        updates: list[WeatherState] = []

        async def update(value: WeatherState) -> None:
            updates.append(value)

        collector = WeatherCollector(
            SETTINGS,
            FakeWeatherGateway([state, RuntimeError("offline"), RuntimeError("offline"), RuntimeError("offline")]),
            update,
        )
        self.assertIs(await collector.poll_once(now=100), state)
        recent = await collector.poll_once(now=500)
        stale = await collector.poll_once(now=2_000)
        expired = await collector.poll_once(now=22_000)
        self.assertFalse(recent.stale)
        self.assertTrue(stale.stale)
        self.assertTrue(stale.available)
        self.assertFalse(expired.available)
        self.assertEqual(len(updates), 3)

    async def test_provider_error_without_cache_is_isolated(self) -> None:
        collector = WeatherCollector(SETTINGS, FakeWeatherGateway([RuntimeError("offline")]), lambda _: None)  # type: ignore[arg-type]
        with self.assertRaises(RuntimeError):
            await collector.poll_once(now=100)


if __name__ == "__main__":
    unittest.main()
