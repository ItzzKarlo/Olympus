from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from olympus_core.models.monitoring import EventSeverity


class MatchPhase(str, Enum):
    NONE = "none"
    UPCOMING = "upcoming"
    PRE_MATCH = "pre_match"
    LIVE = "live"
    HALF_TIME = "half_time"
    FINISHED = "finished"
    POST_MATCH = "post_match"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class MatchPeriod(str, Enum):
    FIRST_HALF = "first_half"
    HALF_TIME = "half_time"
    SECOND_HALF = "second_half"
    EXTRA_TIME = "extra_time"
    PENALTIES = "penalties"
    BREAK = "break"
    UNKNOWN = "unknown"


class FootballEventType(str, Enum):
    GOAL = "goal"
    OWN_GOAL = "own_goal"
    PENALTY_GOAL = "penalty_goal"
    MISSED_PENALTY = "missed_penalty"
    YELLOW_CARD = "yellow_card"
    RED_CARD = "red_card"
    SECOND_YELLOW = "second_yellow"
    SUBSTITUTION = "substitution"
    VAR = "var"
    UNKNOWN = "unknown"


class FootballResult(str, Enum):
    WIN = "win"
    DRAW = "draw"
    LOSS = "loss"
    UNKNOWN = "unknown"


class WatchedPlayerStatus(str, Enum):
    STARTING = "starting"
    PLAYING = "playing"
    SUBSTITUTED = "substituted"
    BENCH = "bench"
    UNAVAILABLE = "unavailable"
    FINISHED = "finished"


class FootballTeam(BaseModel):
    id: str
    name: str
    short_name: str
    code: str | None = None


class FootballCompetition(BaseModel):
    id: str
    name: str


class FootballVenue(BaseModel):
    name: str


class FootballClock(BaseModel):
    minute: int | None = Field(default=None, ge=0)
    added_time: int | None = Field(default=None, ge=0)
    period: MatchPeriod = MatchPeriod.UNKNOWN


class FootballScore(BaseModel):
    home: int | None = Field(default=None, ge=0)
    away: int | None = Field(default=None, ge=0)


class FootballMatch(BaseModel):
    id: str
    competition: FootballCompetition
    kickoff: datetime
    venue: FootballVenue | None = None
    home: FootballTeam
    away: FootballTeam
    status: MatchPhase
    clock: FootballClock | None = None
    score: FootballScore


class FootballPlayer(BaseModel):
    id: str | None = None
    name: str
    number: int | None = None
    position: str | None = None


class FootballLineupPlayer(FootballPlayer):
    starter: bool


class FootballTeamLineup(BaseModel):
    team: FootballTeam
    formation: str | None = None
    players: list[FootballLineupPlayer] = Field(default_factory=list)


class FootballLineups(BaseModel):
    home: FootballTeamLineup | None = None
    away: FootballTeamLineup | None = None


class FootballTeamStatistics(BaseModel):
    possession_percent: float | None = None
    shots: int | None = None
    shots_on_target: int | None = None
    corners: int | None = None
    fouls: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    offsides: int | None = None
    passes: int | None = None
    pass_accuracy_percent: float | None = None


class FootballStatistics(BaseModel):
    home: FootballTeamStatistics | None = None
    away: FootballTeamStatistics | None = None


class FootballPlayerShots(BaseModel):
    total: int | None = None
    on_target: int | None = None


class FootballPlayerPasses(BaseModel):
    total: int | None = None
    key: int | None = None
    accuracy_percent: float | None = None


class FootballPlayerDefending(BaseModel):
    tackles: int | None = None
    interceptions: int | None = None
    blocks: int | None = None


class FootballPlayerDuels(BaseModel):
    total: int | None = None
    won: int | None = None


class FootballPlayerDribbles(BaseModel):
    attempted: int | None = None
    successful: int | None = None


class FootballPlayerFouls(BaseModel):
    committed: int | None = None
    drawn: int | None = None


class FootballPlayerCards(BaseModel):
    yellow: int | None = None
    red: int | None = None


class FootballPlayerPenalties(BaseModel):
    won: int | None = None
    committed: int | None = None
    scored: int | None = None
    missed: int | None = None
    saved: int | None = None


class FootballPlayerStatistics(BaseModel):
    player: FootballPlayer
    team: FootballTeam
    for_tracked_team: bool
    minutes: int | None = None
    rating: float | None = None
    starter: bool | None = None
    goals: int | None = None
    assists: int | None = None
    shots: FootballPlayerShots = Field(default_factory=FootballPlayerShots)
    passes: FootballPlayerPasses = Field(default_factory=FootballPlayerPasses)
    defending: FootballPlayerDefending = Field(default_factory=FootballPlayerDefending)
    duels: FootballPlayerDuels = Field(default_factory=FootballPlayerDuels)
    dribbles: FootballPlayerDribbles = Field(default_factory=FootballPlayerDribbles)
    fouls: FootballPlayerFouls = Field(default_factory=FootballPlayerFouls)
    cards: FootballPlayerCards = Field(default_factory=FootballPlayerCards)
    penalties: FootballPlayerPenalties = Field(default_factory=FootballPlayerPenalties)


class WatchedPlayerState(BaseModel):
    player: FootballPlayer
    status: WatchedPlayerStatus
    rating: float | None = None
    previous_rating: float | None = None
    rating_delta: float | None = None
    statistics: FootballPlayerStatistics | None = None


class FootballRatingSample(BaseModel):
    minute: int | None = None
    rating: float
    observed_at: datetime


class FootballPlayerRatingHistory(BaseModel):
    player: FootballPlayer
    samples: list[FootballRatingSample] = Field(default_factory=list)


class FootballStatisticsSnapshot(BaseModel):
    minute: int | None = None
    home: FootballTeamStatistics | None = None
    away: FootballTeamStatistics | None = None
    observed_at: datetime


class FootballMatchFlowPoint(BaseModel):
    minute: int | None = None
    tracked_team: float = Field(ge=0, le=1)
    opponent: float = Field(ge=0, le=1)
    basis: Literal["statistics", "events", "combined"]
    observed_at: datetime


class FootballQuotaState(BaseModel):
    daily_limit: int | None = None
    daily_remaining: int | None = None
    minute_limit: int | None = None
    minute_remaining: int | None = None
    low: bool = False
    critical: bool = False
    observed_at: datetime


class FootballMatchEvent(BaseModel):
    id: str
    type: FootballEventType
    minute: int | None = Field(default=None, ge=0)
    added_time: int | None = Field(default=None, ge=0)
    team: FootballTeam | None = None
    player: FootballPlayer | None = None
    assist: FootballPlayer | None = None
    score_after: FootballScore | None = None
    for_tracked_team: bool
    detail: str | None = None
    location: dict[str, float | None] | None = None


class ProviderFootballSnapshot(BaseModel):
    tracked_team: FootballTeam
    next_match: FootballMatch | None = None
    match: FootballMatch | None = None
    events: list[FootballMatchEvent] = Field(default_factory=list)
    lineups: FootballLineups | None = None
    statistics: FootballStatistics | None = None
    player_statistics: list[FootballPlayerStatistics] = Field(default_factory=list)
    quota: FootballQuotaState | None = None
    observed_at: datetime


class MatchdayContext(BaseModel):
    active: bool
    phase: MatchPhase
    tracked_team: FootballTeam
    match: FootballMatch
    events: list[FootballMatchEvent] = Field(default_factory=list)
    lineups: FootballLineups | None = None
    statistics: FootballStatistics | None = None
    statistics_history: list[FootballStatisticsSnapshot] = Field(default_factory=list)
    player_statistics: list[FootballPlayerStatistics] = Field(default_factory=list)
    watched_players: list[WatchedPlayerState] = Field(default_factory=list)
    top_tracked_players: list[FootballPlayerStatistics] = Field(default_factory=list)
    top_opponent_players: list[FootballPlayerStatistics] = Field(default_factory=list)
    rating_history: list[FootballPlayerRatingHistory] = Field(default_factory=list)
    match_flow: list[FootballMatchFlowPoint] = Field(default_factory=list)
    result: FootballResult = FootballResult.UNKNOWN
    stale: bool = False
    observed_at: datetime


class FootballState(BaseModel):
    available: bool = True
    stale: bool = False
    observed_at: datetime
    tracked_team: FootballTeam
    next_match: FootballMatch | None = None
    matchday: MatchdayContext | None = None
    quota: FootballQuotaState | None = None


class FootballDisplayEvent(BaseModel):
    id: str
    type: str
    category: Literal["football"] = "football"
    severity: EventSeverity = EventSeverity.INFO
    timestamp: datetime
    source: str = "football"
    payload: dict[str, Any] = Field(default_factory=dict)
