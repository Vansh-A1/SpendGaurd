from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class TimeWindowRule(BaseModel):
    days_of_week: Optional[List[str]] = None
    start: str
    end: str


class Mandate(BaseModel):
    id: str
    agent_id: str
    per_transaction_cap: float
    categories: list[str]
    merchants: list[str]
    time_window_start: str
    time_window_end: str
    issued_at: datetime
    ttl_seconds: int
    time_windows: Optional[List[TimeWindowRule]] = None
    period_caps: Optional[Dict[str, float]] = None
    version: int = 1
