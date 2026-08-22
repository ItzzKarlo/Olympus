from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from olympus_core.models.calendar import CalendarEvent, CalendarEventView, CalendarSnapshot, CalendarState
from olympus_core.models.weather import WeatherState


class WeatherStateStore:
    def __init__(self) -> None:
        self._state: WeatherState | None = None

    def get(self) -> WeatherState | None:
        return self._state

    def update(self, state: WeatherState) -> None:
        self._state = state


def _event_bounds(event: CalendarEvent, zone: ZoneInfo) -> tuple[datetime, datetime]:
    if event.all_day and event.start_date is not None:
        start = datetime.combine(event.start_date, time.min, zone)
        end_date = event.end_date or event.start_date
        end = datetime.combine(end_date, time.min, zone)
        if end <= start:
            end = datetime.combine(date.fromordinal(event.start_date.toordinal() + 1), time.min, zone)
        return start, end
    start = event.start or datetime.max.replace(tzinfo=timezone.utc)
    end = event.end or start
    return start.astimezone(zone), end.astimezone(zone)


def interpret_calendar(snapshot: CalendarSnapshot, timezone_name: str, now: datetime | None = None) -> CalendarState:
    zone = ZoneInfo(timezone_name)
    local_now = (now or datetime.now(timezone.utc)).astimezone(zone)
    today = local_now.date()
    tomorrow = date.fromordinal(today.toordinal() + 1)

    views: list[tuple[datetime, datetime, CalendarEventView]] = []
    for event in snapshot.events:
        start, end = _event_bounds(event, zone)
        if end <= local_now:
            continue
        status = "ongoing" if start <= local_now < end else "future"
        views.append((start, end, CalendarEventView(**event.model_dump(), status=status)))
    views.sort(key=lambda item: (item[0], item[1], item[2].title.casefold()))

    def overlaps(day: date, item: tuple[datetime, datetime, CalendarEventView]) -> bool:
        day_start = datetime.combine(day, time.min, zone)
        day_end = datetime.combine(date.fromordinal(day.toordinal() + 1), time.min, zone)
        return item[0] < day_end and item[1] > day_start

    events = [item[2] for item in views]
    today_events = [item[2] for item in views if overlaps(today, item)]
    tomorrow_events = [item[2] for item in views if overlaps(tomorrow, item)]
    next_event = next((event for event in events if event.status == "ongoing"), events[0] if events else None)
    return CalendarState(
        available=snapshot.available,
        stale=snapshot.stale,
        observed_at=snapshot.observed_at,
        events=events,
        today=today_events,
        tomorrow=tomorrow_events,
        next_event=next_event,
    )


class CalendarStateStore:
    def __init__(self, timezone_name: str = "UTC") -> None:
        self._timezone = timezone_name
        self._snapshot: CalendarSnapshot | None = None

    def get(self, now: datetime | None = None) -> CalendarState | None:
        return interpret_calendar(self._snapshot, self._timezone, now) if self._snapshot is not None else None

    def update(self, snapshot: CalendarSnapshot) -> None:
        self._snapshot = snapshot

    @property
    def has_state(self) -> bool:
        return self._snapshot is not None
