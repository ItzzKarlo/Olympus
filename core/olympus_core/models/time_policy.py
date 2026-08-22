from datetime import datetime

from pydantic import BaseModel


class TimePolicyState(BaseModel):
    is_night: bool
    period_started_at: datetime | None = None
    period_ends_at: datetime | None = None
    next_transition_at: datetime | None = None
