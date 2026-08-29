import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from intent.schema import UserIntent


def compute_intent_hash(
    hard_requirements: Dict[str, Any],
    soft_preferences: Dict[str, Any],
    substitution_allowed: bool,
) -> str:
    """
    Computes a deterministic SHA-256 hash of the canonicalized user intent attributes.
    """
    canonical_payload = {
        "hard_requirements": hard_requirements,
        "soft_preferences": soft_preferences,
        "substitution_allowed": substitution_allowed,
    }
    canonical_bytes = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def create_intent_version(
    base_intent: UserIntent,
    updated_hard_requirements: Optional[Dict[str, Any]] = None,
    updated_soft_preferences: Optional[Dict[str, Any]] = None,
    substitution_allowed: Optional[bool] = None,
    created_at: Optional[datetime] = None,
) -> UserIntent:
    """
    Creates a new immutable version of an existing UserIntent, incrementing intent_version,
    setting parent_intent_id, and calculating the new intent_hash.
    """
    new_hard = (
        updated_hard_requirements
        if updated_hard_requirements is not None
        else base_intent.hard_requirements
    )
    new_soft = (
        updated_soft_preferences
        if updated_soft_preferences is not None
        else base_intent.soft_preferences
    )
    new_sub = (
        substitution_allowed
        if substitution_allowed is not None
        else base_intent.substitution_allowed
    )

    new_version = base_intent.intent_version + 1
    new_id = f"{base_intent.id}_v{new_version}"
    new_hash = compute_intent_hash(new_hard, new_soft, new_sub)
    new_created_at = created_at or datetime.now(timezone.utc)

    return UserIntent(
        id=new_id,
        agent_id=base_intent.agent_id,
        hard_requirements=new_hard,
        soft_preferences=new_soft,
        substitution_allowed=new_sub,
        created_at=new_created_at,
        intent_version=new_version,
        parent_intent_id=base_intent.id,
        intent_hash=new_hash,
    )
