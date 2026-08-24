import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
import logging
import inspect
import time
from uuid import uuid4

from olympus_core.config import FootballSettings
from olympus_core.integrations.football.analytics import FootballAnalytics, RatingChange
from olympus_core.integrations.football.base import FootballProvider, FootballRateLimitError
from olympus_core.models.football import (
    FootballDisplayEvent,
    FootballEventType,
    FootballState,
    MatchdayContext,
    MatchPhase,
    ProviderFootballSnapshot,
)


logger = logging.getLogger(__name__)


PHASE_EVENT_TYPES = {
    (MatchPhase.PRE_MATCH, MatchPhase.LIVE): "football.match.started",
    (MatchPhase.UPCOMING, MatchPhase.LIVE): "football.match.started",
    (MatchPhase.LIVE, MatchPhase.HALF_TIME): "football.half_time",
    (MatchPhase.HALF_TIME, MatchPhase.LIVE): "football.match.resumed",
    (MatchPhase.SUSPENDED, MatchPhase.LIVE): "football.match.resumed",
    (MatchPhase.LIVE, MatchPhase.FINISHED): "football.match.finished",
    (MatchPhase.HALF_TIME, MatchPhase.FINISHED): "football.match.finished",
}

FOOTBALL_EVENT_TYPES = {
    FootballEventType.GOAL: "football.goal",
    FootballEventType.OWN_GOAL: "football.goal",
    FootballEventType.PENALTY_GOAL: "football.goal",
    FootballEventType.MISSED_PENALTY: "football.missed_penalty",
    FootballEventType.YELLOW_CARD: "football.yellow_card",
    FootballEventType.RED_CARD: "football.red_card",
    FootballEventType.SECOND_YELLOW: "football.red_card",
    FootballEventType.SUBSTITUTION: "football.substitution",
    FootballEventType.VAR: "football.var",
    FootballEventType.UNKNOWN: "football.event",
}


class MatchdayPolicy:
    def __init__(self, settings: FootballSettings) -> None:
        self._settings = settings
        self._finished_match_id: str | None = None
        self._finished_seen_at: datetime | None = None

    def state(self, snapshot: ProviderFootballSnapshot, now: datetime | None = None) -> FootballState:
        current = now or datetime.now(timezone.utc)
        match = snapshot.match
        context = None
        if match is not None:
            phase = match.status
            active = False
            if phase == MatchPhase.UPCOMING:
                if current >= match.kickoff - timedelta(minutes=self._settings.matchday.pre_match_minutes):
                    phase = MatchPhase.PRE_MATCH
                    active = True
            elif phase in {MatchPhase.LIVE, MatchPhase.HALF_TIME, MatchPhase.SUSPENDED}:
                active = True
                self._finished_match_id = None
                self._finished_seen_at = None
            elif phase == MatchPhase.FINISHED:
                if self._finished_match_id != match.id:
                    self._finished_match_id = match.id
                    self._finished_seen_at = current
                if self._finished_seen_at and current < self._finished_seen_at + timedelta(minutes=self._settings.matchday.post_match_minutes):
                    phase = MatchPhase.POST_MATCH
                    active = True
            if active:
                context = MatchdayContext(
                    active=True,
                    phase=phase,
                    tracked_team=snapshot.tracked_team,
                    match=match,
                    events=snapshot.events,
                    lineups=snapshot.lineups,
                    statistics=snapshot.statistics,
                    observed_at=snapshot.observed_at,
                )
        return FootballState(
            observed_at=snapshot.observed_at,
            tracked_team=snapshot.tracked_team,
            next_match=snapshot.next_match,
            matchday=context,
            quota=snapshot.quota,
        )


class FootballCollector:
    def __init__(
        self,
        settings: FootballSettings,
        provider: FootballProvider,
        on_update: Callable[[FootballState], Awaitable[None]],
        on_event: Callable[[FootballDisplayEvent], Awaitable[None]],
        *,
        monotonic_clock: Callable[[], float] | None = None,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._on_update = on_update
        self._on_event = on_event
        self._policy = MatchdayPolicy(settings)
        self._monotonic = monotonic_clock or time.monotonic
        self._stop = asyncio.Event()
        self._last_good: FootballState | None = None
        self._last_success_at: float | None = None
        self._published: FootballState | None = None
        self._last_error_log_at = 0.0
        self._retry_after: float | None = None
        self._match_id: str | None = None
        self._phase: MatchPhase | None = None
        self._seen_event_ids: set[str] = set()
        self._lineup_available = False
        self._analytics = FootballAnalytics(settings)
        self._minimum_poll_seconds = max(0.0, getattr(provider, "minimum_poll_seconds", 0.0))
        self._post_match_minimum_poll_seconds = max(
            self._minimum_poll_seconds,
            getattr(provider, "post_match_minimum_poll_seconds", 0.0),
        )

    async def _publish(self, state: FootballState) -> FootballState:
        if state != self._published:
            self._published = state
            result = self._on_update(state)
            if inspect.isawaitable(result):
                await result
        return state

    async def _notify_event(self, event: FootballDisplayEvent) -> None:
        result = self._on_event(event)
        if inspect.isawaitable(result):
            await result

    async def _emit_rating_changes(self, match_id: str, observed_at: datetime, changes: list[RatingChange]) -> None:
        for change in changes:
            await self._notify_event(FootballDisplayEvent(
                id=f"rating:{match_id}:{change.player.id or change.player.name}:{observed_at.isoformat()}",
                type="football.player.rating_changed",
                timestamp=observed_at,
                payload={
                    "match_id": match_id,
                    "player": change.player.model_dump(mode="json"),
                    "previous_rating": change.previous,
                    "rating": change.current,
                    "delta": round(change.delta, 2),
                    "for_tracked_team": True,
                },
            ))

    def _effective_phase(self, snapshot: ProviderFootballSnapshot, state: FootballState) -> MatchPhase:
        if state.matchday is not None:
            return state.matchday.phase
        return snapshot.match.status if snapshot.match is not None else MatchPhase.NONE

    async def _emit_changes(self, snapshot: ProviderFootballSnapshot, state: FootballState) -> None:
        match = snapshot.match
        if match is None:
            self._match_id = None
            self._phase = MatchPhase.NONE
            self._seen_event_ids.clear()
            self._lineup_available = False
            return
        phase = self._effective_phase(snapshot, state)
        if self._match_id != match.id:
            self._match_id = match.id
            self._phase = phase
            self._seen_event_ids = {event.id for event in snapshot.events}
            self._lineup_available = snapshot.lineups is not None
            return

        phase_event = PHASE_EVENT_TYPES.get((self._phase or MatchPhase.NONE, match.status))
        if phase_event is not None:
            await self._notify_event(FootballDisplayEvent(
                id=uuid4().hex,
                type=phase_event,
                timestamp=snapshot.observed_at,
                payload={"match_id": match.id},
            ))
        self._phase = phase

        for event in snapshot.events:
            if event.id in self._seen_event_ids:
                continue
            self._seen_event_ids.add(event.id)
            await self._notify_event(FootballDisplayEvent(
                id=event.id,
                type=FOOTBALL_EVENT_TYPES[event.type],
                timestamp=snapshot.observed_at,
                payload={"match_id": match.id, "event": event.model_dump(mode="json")},
            ))

        lineup_available = snapshot.lineups is not None and any(
            lineup is not None and any(player.starter for player in lineup.players)
            for lineup in (snapshot.lineups.home, snapshot.lineups.away)
        )
        if lineup_available and not self._lineup_available:
            await self._notify_event(FootballDisplayEvent(
                id=uuid4().hex,
                type="football.lineup.available",
                timestamp=snapshot.observed_at,
                payload={"match_id": match.id},
            ))
        self._lineup_available = lineup_available

    async def poll_once(self, *, monotonic_now: float | None = None, now: datetime | None = None) -> FootballState:
        tick = self._monotonic() if monotonic_now is None else monotonic_now
        try:
            snapshot = await self._provider.fetch()
            state = self._policy.state(snapshot, now)
        except Exception as error:
            if isinstance(error, FootballRateLimitError):
                self._retry_after = error.retry_after
            if tick - self._last_error_log_at >= 30:
                logger.warning("Football provider temporarily unavailable: %s", error)
                self._last_error_log_at = tick
            if self._last_good is None or self._last_success_at is None:
                raise
            age = tick - self._last_success_at
            live = self._last_good.matchday is not None and self._last_good.matchday.phase in {
                MatchPhase.LIVE, MatchPhase.HALF_TIME, MatchPhase.SUSPENDED,
            }
            stale = age > (self._settings.live_stale_seconds if live else self._settings.poll_upcoming_seconds * 2)
            context = self._last_good.matchday.model_copy(update={"stale": stale}) if self._last_good.matchday else None
            return await self._publish(self._last_good.model_copy(update={
                "available": age <= self._settings.unavailable_seconds,
                "stale": stale,
                "matchday": context,
            }))

        self._retry_after = None
        rating_changes: list[RatingChange] = []
        if state.matchday is not None:
            context, rating_changes = self._analytics.enrich(snapshot, state.matchday, tick)
            state = state.model_copy(update={"matchday": context})
        self._last_good = state
        self._last_success_at = tick
        published = await self._publish(state)
        await self._emit_changes(snapshot, state)
        if snapshot.match is not None:
            await self._emit_rating_changes(snapshot.match.id, snapshot.observed_at, rating_changes)
        return published

    def poll_interval(self, state: FootballState, now: datetime | None = None) -> float:
        minimum = (
            self._post_match_minimum_poll_seconds
            if state.matchday is not None and state.matchday.phase == MatchPhase.POST_MATCH
            else self._minimum_poll_seconds
        )
        if self._retry_after is not None:
            return max(
                self._retry_after,
                self._settings.poll_pre_match_seconds,
                minimum,
            )
        if state.matchday is not None:
            interval = {
                MatchPhase.LIVE: self._settings.poll_live_seconds,
                MatchPhase.HALF_TIME: self._settings.poll_half_time_seconds,
                MatchPhase.SUSPENDED: self._settings.poll_half_time_seconds,
                MatchPhase.PRE_MATCH: self._settings.poll_pre_match_seconds,
                MatchPhase.POST_MATCH: self._settings.poll_post_match_seconds,
            }.get(state.matchday.phase, self._settings.poll_post_match_seconds)
            if state.quota and state.quota.critical:
                return max(interval, 60.0, minimum)
            if state.quota and state.quota.low:
                return max(interval, 30.0, minimum)
            return max(interval, minimum)
        current = now or datetime.now(timezone.utc)
        if state.next_match is not None and state.next_match.kickoff - current <= timedelta(hours=24):
            return max(self._settings.poll_near_match_seconds, minimum)
        return max(self._settings.poll_upcoming_seconds, minimum)

    async def run(self) -> None:
        logger.info("Football collector enabled for %s", self._settings.team_name)
        try:
            while not self._stop.is_set():
                state: FootballState | None = None
                try:
                    state = await self.poll_once()
                except Exception:
                    pass
                interval = self.poll_interval(state or self._last_good) if (state or self._last_good) else self._settings.poll_pre_match_seconds
                try:
                    await asyncio.wait_for(self._stop.wait(), interval)
                except TimeoutError:
                    pass
        finally:
            await self._provider.aclose()

    def stop(self) -> None:
        self._stop.set()
