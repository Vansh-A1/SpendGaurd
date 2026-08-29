from datetime import datetime
from pydantic import BaseModel


class UserIntent(BaseModel):
    id: str
    agent_id: str
    hard_requirements: dict
    soft_preferences: dict
    substitution_allowed: bool
    created_at: datetime
