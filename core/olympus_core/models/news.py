from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

from olympus_core.models.monitoring import EventSeverity


class NewsTopic(str, Enum):
    WORLD = "world"
    GERMANY = "germany"
    LOCAL = "local"
    POLITICS = "politics"
    ECONOMY = "economy"
    TECHNOLOGY = "technology"
    SCIENCE = "science"
    WEATHER = "weather"
    TRANSPORT = "transport"
    SPORTS = "sports"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


class NewsImportanceLevel(str, Enum):
    AMBIENT = "ambient"
    NOTABLE = "notable"
    IMPORTANT = "important"
    MAJOR = "major"


class NewsSource(BaseModel):
    id: str
    name: str
    language: str
    region: str | None = None
    trust: float = Field(default=1.0, ge=0.1, le=2.0)


class NewsArticle(BaseModel):
    id: str
    provider_id: str | None = None
    headline: str
    source: NewsSource
    url: HttpUrl
    canonical_url: str
    published_at: datetime | None = None
    observed_at: datetime
    summary: str | None = None
    language: str
    categories: list[str] = Field(default_factory=list)
    topic: NewsTopic = NewsTopic.OTHER


class NewsImportance(BaseModel):
    score: float = Field(ge=0, le=1)
    level: NewsImportanceLevel
    factors: dict[str, float] = Field(default_factory=dict)


class NewsCluster(BaseModel):
    id: str
    headline: str
    summary: str | None = None
    language: str
    topic: NewsTopic
    articles: list[NewsArticle]
    sources: list[NewsSource]
    first_seen_at: datetime
    latest_seen_at: datetime
    importance: NewsImportance


class NewsPresentation(BaseModel):
    active: bool = True
    story_id: str
    level: NewsImportanceLevel
    started_at: datetime
    ends_at: datetime


class NewsFeedHealth(BaseModel):
    feed_id: str
    last_success_at: datetime | None = None
    last_error: str | None = None
    stale: bool = False


class NewsState(BaseModel):
    available: bool = True
    last_updated_at: datetime | None = None
    stale: bool = False
    top_stories: list[NewsCluster] = Field(default_factory=list)
    ambient: list[NewsCluster] = Field(default_factory=list)
    active_story: NewsCluster | None = None
    presentation: NewsPresentation | None = None
    feed_health: list[NewsFeedHealth] = Field(default_factory=list)


class NewsDisplayEvent(BaseModel):
    id: str
    type: str
    category: Literal["news"] = "news"
    severity: EventSeverity = EventSeverity.INFO
    timestamp: datetime
    source: str = "news"
    payload: dict[str, Any] = Field(default_factory=dict)

