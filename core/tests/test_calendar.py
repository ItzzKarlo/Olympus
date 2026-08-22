from datetime import date, datetime, timezone
import os
import unittest
from unittest.mock import patch

import httpx

from olympus_core.config import CalendarSettings, parse_core_config
from olympus_core.integrations.calendar import CalendarCollector, GoogleCalendarApi, normalize_google_event
from olympus_core.models.calendar import CalendarEvent, CalendarSnapshot
from olympus_core.services.ambient import interpret_calendar


SETTINGS = CalendarSettings(
    enabled=True,
    timezone="Europe/Berlin",
    lookahead_days=7,
    poll_seconds=300,
    stale_seconds=1_800,
    unavailable_seconds=21_600,
    calendar_ids=("primary", "work"),
    client_id="client",
    client_secret="secret",
    refresh_token="refresh",
)


def timed(event_id: str, title: str, start: str, end: str, **extra: object) -> dict[str, object]:
    return {
        "id": event_id,
        "summary": title,
        "status": "confirmed",
        "start": {"dateTime": start},
        "end": {"dateTime": end},
        **extra,
    }


def all_day(event_id: str, title: str, start: str, end: str) -> dict[str, object]:
    return {
        "id": event_id,
        "summary": title,
        "status": "confirmed",
        "start": {"date": start},
        "end": {"date": end},
    }


class CalendarNormalizationTests(unittest.TestCase):
    def test_timed_all_day_cancelled_and_limited_fields(self) -> None:
        timed_event = normalize_google_event(
            timed(
                "meeting",
                "Appointment",
                "2026-08-23T10:30:00+02:00",
                "2026-08-23T11:30:00+02:00",
                location="Studio",
                description="private notes",
                attendees=[{"email": "private@example.com"}],
            ),
            "primary",
            "Personal",
            "Europe/Berlin",
        )
        day_event = normalize_google_event(
            all_day("birthday", "Birthday", "2026-08-23", "2026-08-24"),
            "primary",
            "Personal",
            "Europe/Berlin",
        )
        cancelled = normalize_google_event(
            {**timed("gone", "Gone", "2026-08-23T12:00:00+02:00", "2026-08-23T13:00:00+02:00"), "status": "cancelled"},
            "primary",
            "Personal",
            "Europe/Berlin",
        )
        self.assertFalse(timed_event.all_day)
        self.assertEqual(timed_event.location, "Studio")
        self.assertFalse(hasattr(timed_event, "description"))
        self.assertTrue(day_event.all_day)
        self.assertEqual(day_event.start_date, date(2026, 8, 23))
        self.assertIsNone(day_event.start)
        self.assertIsNone(cancelled)

    def test_disabled_calendar_and_credentials_are_optional(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            disabled = parse_core_config({})
            enabled = parse_core_config({"calendar": {"enabled": True}})
        self.assertFalse(disabled.calendar.enabled)
        self.assertFalse(enabled.calendar.configured)

    def test_configures_multiple_calendars_from_toml_and_secrets_from_environment(self) -> None:
        with patch.dict(os.environ, {
            "OLYMPUS_GOOGLE_CLIENT_ID": "client",
            "OLYMPUS_GOOGLE_CLIENT_SECRET": "secret",
            "OLYMPUS_GOOGLE_REFRESH_TOKEN": "refresh",
        }, clear=True):
            config = parse_core_config({
                "olympus": {"timezone": "Europe/Berlin"},
                "calendar": {
                    "enabled": True,
                    "calendar_ids": ["primary", "work"],
                    "lookahead_days": 14,
                    "poll_minutes": 6,
                },
            })
        self.assertTrue(config.calendar.configured)
        self.assertEqual(config.calendar.calendar_ids, ("primary", "work"))
        self.assertEqual(config.calendar.lookahead_days, 14)
        self.assertEqual(config.calendar.poll_seconds, 360)


class CalendarApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_refreshes_auth_merges_calendars_expands_instances_and_orders(self) -> None:
        token_requests = 0
        calendar_requests = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal token_requests, calendar_requests
            if request.url.host == "oauth2.googleapis.com":
                token_requests += 1
                return httpx.Response(200, json={"access_token": f"token-{token_requests}", "expires_in": 3600})
            calendar_requests += 1
            self.assertEqual(request.url.params["singleEvents"], "true")
            self.assertEqual(request.url.params["orderBy"], "startTime")
            if calendar_requests == 1:
                return httpx.Response(401)
            if "/primary/" in request.url.path:
                return httpx.Response(200, json={
                    "summary": "Personal",
                    "items": [
                        timed("late", "Late", "2099-08-23T18:00:00+02:00", "2099-08-23T19:00:00+02:00"),
                        all_day("day", "All day", "2099-08-23", "2099-08-24"),
                    ],
                })
            return httpx.Response(200, json={
                "summary": "Work",
                "items": [
                    timed("recurring-instance", "Standup", "2099-08-23T09:00:00+02:00", "2099-08-23T09:30:00+02:00", recurringEventId="series"),
                    {**timed("cancelled", "Cancelled", "2099-08-23T08:00:00+02:00", "2099-08-23T09:00:00+02:00"), "status": "cancelled"},
                ],
            })

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        snapshot = await GoogleCalendarApi(SETTINGS, client).fetch()
        await client.aclose()
        self.assertEqual(token_requests, 2)
        self.assertEqual([event.title for event in snapshot.events], ["All day", "Standup", "Late"])
        self.assertEqual(snapshot.events[1].calendar_name, "Work")
        self.assertEqual(len(snapshot.events), 3)


class CalendarInterpretationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = CalendarSnapshot(
            observed_at=datetime(2026, 8, 22, 18, tzinfo=timezone.utc),
            events=[
                CalendarEvent(
                    id="past", title="Past", start=datetime.fromisoformat("2026-08-22T18:00:00+02:00"),
                    end=datetime.fromisoformat("2026-08-22T19:00:00+02:00"), calendar_id="primary", calendar_name="Personal",
                ),
                CalendarEvent(
                    id="ongoing", title="Dinner", start=datetime.fromisoformat("2026-08-22T20:00:00+02:00"),
                    end=datetime.fromisoformat("2026-08-22T21:00:00+02:00"), calendar_id="primary", calendar_name="Personal",
                ),
                CalendarEvent(
                    id="later", title="Late call", start=datetime.fromisoformat("2026-08-22T23:30:00+02:00"),
                    end=datetime.fromisoformat("2026-08-23T00:30:00+02:00"), calendar_id="work", calendar_name="Work",
                ),
                CalendarEvent(
                    id="tomorrow", title="Birthday", all_day=True, start_date=date(2026, 8, 23), end_date=date(2026, 8, 24),
                    calendar_id="primary", calendar_name="Personal",
                ),
            ],
        )

    def test_today_tomorrow_ongoing_next_and_past_filtering(self) -> None:
        state = interpret_calendar(
            self.snapshot,
            "Europe/Berlin",
            datetime.fromisoformat("2026-08-22T20:30:00+02:00"),
        )
        self.assertEqual([event.title for event in state.today], ["Dinner", "Late call"])
        self.assertEqual([event.title for event in state.tomorrow], ["Late call", "Birthday"])
        self.assertEqual(state.next_event.title, "Dinner")
        self.assertEqual(state.next_event.status, "ongoing")
        self.assertNotIn("Past", [event.title for event in state.events])

    def test_utc_day_boundary_and_dst_use_timezone_database(self) -> None:
        boundary = CalendarSnapshot(
            observed_at=datetime.now(timezone.utc),
            events=[CalendarEvent(
                id="dst", title="DST morning", start=datetime.fromisoformat("2026-03-29T09:00:00+02:00"),
                end=datetime.fromisoformat("2026-03-29T10:00:00+02:00"), calendar_id="primary", calendar_name="Personal",
            )],
        )
        state = interpret_calendar(boundary, "Europe/Berlin", datetime.fromisoformat("2026-03-28T23:30:00+00:00"))
        self.assertEqual(state.today[0].title, "DST morning")
        self.assertEqual(state.today[0].start.utcoffset().total_seconds(), 7_200)


class FakeCalendarGateway:
    def __init__(self, outcomes: list[CalendarSnapshot | Exception]) -> None:
        self.outcomes = outcomes

    async def fetch(self) -> CalendarSnapshot:
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def aclose(self) -> None:
        return None


class CalendarCollectorTests(unittest.IsolatedAsyncioTestCase):
    async def test_failure_retains_then_stales_and_expires_state(self) -> None:
        snapshot = CalendarSnapshot(observed_at=datetime.now(timezone.utc), events=[])
        updates: list[CalendarSnapshot] = []

        async def update(state: CalendarSnapshot) -> None:
            updates.append(state)

        collector = CalendarCollector(
            SETTINGS,
            FakeCalendarGateway([snapshot, RuntimeError("offline"), RuntimeError("offline"), RuntimeError("offline")]),
            update,
        )
        await collector.poll_once(now=100)
        recent = await collector.poll_once(now=500)
        stale = await collector.poll_once(now=2_000)
        expired = await collector.poll_once(now=22_000)
        self.assertFalse(recent.stale)
        self.assertTrue(stale.stale)
        self.assertTrue(stale.available)
        self.assertFalse(expired.available)
        self.assertEqual(len(updates), 3)


if __name__ == "__main__":
    unittest.main()
