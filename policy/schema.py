from datetime import datetime
from pydantic import BaseModel


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
