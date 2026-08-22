from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from olympus_core.config import NightSettings
from olympus_core.models.time_policy import TimePolicyState


class TimePolicyService:
    """Resolves environmental time policy in the configured room timezone."""

    def __init__(self, settings: NightSettings, timezone_name: str) -> None:
        self.settings = settings
        self._zone = ZoneInfo(timezone_name)

    def _period_for_evening(self, evening: date) -> tuple[datetime, datetime]:
        start_time = (
            self.settings.weekend_start
            if evening.weekday() in self.settings.weekend_days
            else self.settings.weekday_start
        )
        # Midnight belongs to the end of the named evening, not its beginning.
        start_date = date.fromordinal(evening.toordinal() + 1) if start_time == time.min else evening
        start = datetime.combine(start_date, start_time, self._zone)
        end_date = start_date
        if self.settings.end <= start_time:
            end_date = date.fromordinal(start_date.toordinal() + 1)
        end = datetime.combine(end_date, self.settings.end, self._zone)
        return start, end

    def evaluate(self, now: datetime | None = None) -> TimePolicyState:
        instant = now or datetime.now(timezone.utc)
        if instant.tzinfo is None:
            raise ValueError("Time policy requires a timezone-aware datetime")
        local_now = instant.astimezone(self._zone)
        if not self.settings.enabled:
            return TimePolicyState(is_night=False)

        periods = [
            self._period_for_evening(date.fromordinal(local_now.date().toordinal() + offset))
            for offset in range(-2, 9)
        ]
        active = next(
            ((start, end) for start, end in periods if start <= local_now < end),
            None,
        )
        if active is not None:
            return TimePolicyState(
                is_night=True,
                period_started_at=active[0],
                period_ends_at=active[1],
                next_transition_at=active[1],
            )
        next_start = min(start for start, _ in periods if start > local_now)
        return TimePolicyState(is_night=False, next_transition_at=next_start)

    def is_night(self, now: datetime | None = None) -> bool:
        return self.evaluate(now).is_night
