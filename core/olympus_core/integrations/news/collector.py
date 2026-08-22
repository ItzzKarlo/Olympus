import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import inspect
import logging
from uuid import uuid4

from olympus_core.config import NewsSettings
from olympus_core.integrations.news.base import NewsProvider
from olympus_core.integrations.news.engine import NewsEngine
from olympus_core.models.news import (
    NewsCluster,
    NewsDisplayEvent,
    NewsImportanceLevel,
    NewsPresentation,
    NewsState,
)
from olympus_core.integrations.news.normalization import normalize_headline
from olympus_core.persistence.news_memory import NewsMemoryRepository


LEVEL_RANK = {
    NewsImportanceLevel.AMBIENT: 0,
    NewsImportanceLevel.NOTABLE: 1,
    NewsImportanceLevel.IMPORTANT: 2,
    NewsImportanceLevel.MAJOR: 3,
}
logger = logging.getLogger(__name__)


def cluster_fingerprint(cluster: NewsCluster) -> str:
    tokens = sorted(set(normalize_headline(cluster.headline).split()))
    identity = f"{cluster.topic.value}\0{' '.join(tokens)}"
    return sha256(identity.encode("utf-8")).hexdigest()


class NewsCollector:
    def __init__(
        self,
        settings: NewsSettings,
        provider: NewsProvider,
        on_update: Callable[[NewsState], Awaitable[None] | None],
        on_event: Callable[[NewsDisplayEvent], Awaitable[None] | None],
        memory: NewsMemoryRepository | None = None,
        memory_retention_days: int = 7,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._on_update = on_update
        self._on_event = on_event
        self._engine = NewsEngine(settings)
        self._state = NewsState(available=False)
        self._baseline_established = False
        self._known_levels: dict[str, NewsImportanceLevel] = {}
        self._presented: dict[str, tuple[NewsImportanceLevel, datetime]] = {}
        self._memory = memory
        if memory is not None:
            self._presented = {
                fingerprint: (NewsImportanceLevel(item.highest_level), item.last_presented_at)
                for fingerprint, item in memory.load(memory_retention_days).items()
            }
        self._expiry_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._lock = asyncio.Lock()

    async def _publish(self, state: NewsState) -> None:
        self._state = state
        result = self._on_update(state)
        if inspect.isawaitable(result):
            await result

    async def _notify(self, cluster: NewsCluster, observed_at: datetime) -> None:
        event = NewsDisplayEvent(
            id=uuid4().hex,
            type=f"news.story.{cluster.importance.level.value}",
            timestamp=observed_at,
            payload={"story": cluster.model_dump(mode="json")},
        )
        result = self._on_event(event)
        if inspect.isawaitable(result):
            await result

    def _escalations(self, clusters: list[NewsCluster]) -> list[NewsCluster]:
        escalations: list[NewsCluster] = []
        for cluster in clusters:
            level = cluster.importance.level
            previous = self._known_levels.get(cluster.id)
            if LEVEL_RANK[level] < LEVEL_RANK[NewsImportanceLevel.NOTABLE]:
                continue
            if previous is not None and LEVEL_RANK[level] <= LEVEL_RANK[previous]:
                continue
            escalations.append(cluster)
        return escalations

    def _candidate(self, escalations: list[NewsCluster], now: datetime) -> NewsCluster | None:
        eligible: list[NewsCluster] = []
        for cluster in escalations:
            level = cluster.importance.level
            if LEVEL_RANK[level] < LEVEL_RANK[NewsImportanceLevel.IMPORTANT]:
                continue
            presented = self._presented.get(cluster_fingerprint(cluster))
            if presented is not None:
                prior_level, prior_at = presented
                in_cooldown = now - prior_at < timedelta(seconds=self._settings.presentation.cooldown_seconds)
                if in_cooldown and LEVEL_RANK[level] <= LEVEL_RANK[prior_level]:
                    continue
            eligible.append(cluster)
        return max(
            eligible,
            key=lambda cluster: (LEVEL_RANK[cluster.importance.level], cluster.importance.score, cluster.latest_seen_at),
            default=None,
        )

    async def _expire_after(self, ends_at: datetime) -> None:
        delay = max(0.0, (ends_at - datetime.now(timezone.utc)).total_seconds())
        try:
            await asyncio.sleep(delay)
            async with self._lock:
                presentation = self._state.presentation
                if presentation is not None and presentation.ends_at <= datetime.now(timezone.utc):
                    await self._publish(self._state.model_copy(update={
                        "active_story": None,
                        "presentation": None,
                    }))
        except asyncio.CancelledError:
            return

    async def _present(self, cluster: NewsCluster, now: datetime, state: NewsState) -> NewsState:
        current = self._state.presentation
        if current is not None and LEVEL_RANK[current.level] >= LEVEL_RANK[cluster.importance.level]:
            return state.model_copy(update={
                "active_story": self._state.active_story,
                "presentation": current,
            })
        seconds = (
            self._settings.presentation.major_scene_seconds
            if cluster.importance.level == NewsImportanceLevel.MAJOR
            else self._settings.presentation.news_scene_seconds
        )
        presentation = NewsPresentation(
            story_id=cluster.id,
            level=cluster.importance.level,
            started_at=now,
            ends_at=now + timedelta(seconds=seconds),
        )
        fingerprint = cluster_fingerprint(cluster)
        self._presented[fingerprint] = (cluster.importance.level, now)
        if self._memory is not None:
            try:
                self._memory.record(fingerprint, cluster.importance.level.value, now)
            except Exception as error:
                logger.warning("Could not persist News presentation memory: %s", error)
        if self._expiry_task is not None:
            self._expiry_task.cancel()
        self._expiry_task = asyncio.create_task(self._expire_after(presentation.ends_at))
        return state.model_copy(update={"active_story": cluster, "presentation": presentation})

    async def poll_once(self, now: datetime | None = None) -> NewsState:
        current = now or datetime.now(timezone.utc)
        results = await self._provider.fetch()
        async with self._lock:
            state = self._engine.update(results, current)
            escalations = self._escalations(state.top_stories) if self._baseline_established else []
            candidate = self._candidate(escalations, current)
            if self._state.presentation is not None and self._state.presentation.ends_at > current:
                active = next(
                    (cluster for cluster in state.top_stories if cluster.id == self._state.presentation.story_id),
                    self._state.active_story,
                )
                state = state.model_copy(update={
                    "active_story": active,
                    "presentation": self._state.presentation,
                })
            if candidate is not None:
                state = await self._present(candidate, current, state)
            await self._publish(state)
            for cluster in escalations:
                await self._notify(cluster, current)
            self._known_levels = {cluster.id: cluster.importance.level for cluster in state.top_stories}
            self._baseline_established = True
            return state

    async def run(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    await self.poll_once()
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(self._stop.wait(), self._settings.poll_seconds)
                except TimeoutError:
                    pass
        finally:
            if self._expiry_task is not None:
                self._expiry_task.cancel()
                await asyncio.gather(self._expiry_task, return_exceptions=True)
            await self._provider.aclose()

    def stop(self) -> None:
        self._stop.set()
