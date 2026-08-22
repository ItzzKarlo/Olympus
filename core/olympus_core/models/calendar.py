from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime | None = None
    end: datetime | None = None
    start_date: date | None = None
    end_date: date | None = None
    all_day: bool = False
    location: str | None = None
    calendar_id: str
    calendar_name: str


class CalendarEventView(CalendarEvent):
    status: Literal["future", "ongoing"]


class CalendarSnapshot(BaseModel):
    available: bool = True
    stale: bool = False
    observed_at: datetime
    events: list[CalendarEvent]


class CalendarState(BaseModel):
    available: bool = True
    stale: bool = False
    observed_at: datetime
    events: list[CalendarEventView]
    today: list[CalendarEventView]
    tomorrow: list[CalendarEventView]
    next_event: CalendarEventView | None = None
