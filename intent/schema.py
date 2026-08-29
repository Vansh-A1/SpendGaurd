import hashlib
import json
from datetime import datetime
from typing import Optional, Any, Union, Dict
from pydantic import BaseModel, model_validator


class WeightedPreference(BaseModel):
    val: Any
    weight: float = 1.0


class UserIntent(BaseModel):
    id: str
    agent_id: str
    hard_requirements: dict
    soft_preferences: dict
    substitution_allowed: bool
    created_at: datetime
    intent_version: int = 1
    parent_intent_id: Optional[str] = None
    intent_hash: Optional[str] = None

    @model_validator(mode="after")
    def populate_intent_hash(self) -> "UserIntent":
        if not self.intent_hash:
            canonical_payload = {
                "hard_requirements": self.hard_requirements,
                "soft_preferences": self.soft_preferences,
                "substitution_allowed": self.substitution_allowed,
            }
            canonical_bytes = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.intent_hash = hashlib.sha256(canonical_bytes).hexdigest()
        return self
