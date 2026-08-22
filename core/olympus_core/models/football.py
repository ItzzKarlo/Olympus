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


class FootballLineupPlayer(FootballPlayer):
    number: int | None = None
    position: str | None = None
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


class ProviderFootballSnapshot(BaseModel):
    tracked_team: FootballTeam
    next_match: FootballMatch | None = None
    match: FootballMatch | None = None
    events: list[FootballMatchEvent] = Field(default_factory=list)
    lineups: FootballLineups | None = None
    statistics: FootballStatistics | None = None
    observed_at: datetime


class MatchdayContext(BaseModel):
    active: bool
    phase: MatchPhase
    tracked_team: FootballTeam
    match: FootballMatch
    events: list[FootballMatchEvent] = Field(default_factory=list)
    lineups: FootballLineups | None = None
    statistics: FootballStatistics | None = None
    stale: bool = False
    observed_at: datetime


class FootballState(BaseModel):
    available: bool = True
    stale: bool = False
    observed_at: datetime
    tracked_team: FootballTeam
    next_match: FootballMatch | None = None
    matchday: MatchdayContext | None = None


class FootballDisplayEvent(BaseModel):
    id: str
    type: str
    category: Literal["football"] = "football"
    severity: EventSeverity = EventSeverity.INFO
    timestamp: datetime
    source: str = "football"
    payload: dict[str, Any] = Field(default_factory=dict)

