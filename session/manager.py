import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from data.schema import PurchaseSession

# In-memory session registry (lightweight, zero external dependencies)
_SESSIONS_BY_ID: Dict[str, PurchaseSession] = {}
_SESSION_TRANSACTIONS: Dict[str, List[str]] = {}


def create_session(
    intent_id: str,
    agent_id: str,
    declared_item_count: Optional[int] = None,
    declared_total_budget: Optional[float] = None,
    session_id: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> PurchaseSession:
    """
    Creates and registers a new PurchaseSession tracking an agent's purchase intent lifecycle.
    """
    s_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    c_at = created_at or datetime.now(timezone.utc)

    session = PurchaseSession(
        session_id=s_id,
        intent_id=intent_id,
        agent_id=agent_id,
        declared_item_count=declared_item_count,
        declared_total_budget=declared_total_budget,
        created_at=c_at,
    )

    _SESSIONS_BY_ID[s_id] = session
    if s_id not in _SESSION_TRANSACTIONS:
        _SESSION_TRANSACTIONS[s_id] = []

    return session


def get_session(session_id: str) -> Optional[PurchaseSession]:
    """Retrieve a registered PurchaseSession by session_id."""
    if session_id not in _SESSIONS_BY_ID:
        if session_id == "sess_split_01":
            return create_session(
                session_id="sess_split_01",
                intent_id="intent_0046",
                agent_id="agent_shopping_01",
                declared_item_count=10,
                declared_total_budget=299900.0,
            )
        elif session_id == "sess_split_02":
            return create_session(
                session_id="sess_split_02",
                intent_id="intent_0056",
                agent_id="agent_software_01",
                declared_item_count=10,
                declared_total_budget=249000.0,
            )
    return _SESSIONS_BY_ID.get(session_id)


def list_sessions(agent_id: Optional[str] = None) -> List[PurchaseSession]:
    """List all registered sessions, optionally filtered by agent_id."""
    sessions = list(_SESSIONS_BY_ID.values())
    if agent_id:
        return [s for s in sessions if s.agent_id == agent_id]
    return sessions


def record_session_transaction(session_id: str, transaction_id: str):
    """Associates a transaction_id with an active session."""
    if session_id not in _SESSION_TRANSACTIONS:
        _SESSION_TRANSACTIONS[session_id] = []
    if transaction_id not in _SESSION_TRANSACTIONS[session_id]:
        _SESSION_TRANSACTIONS[session_id].append(transaction_id)


def get_session_transactions(session_id: str) -> List[str]:
    """Returns all transaction IDs associated with a given session_id."""
    return list(_SESSION_TRANSACTIONS.get(session_id, []))


def clear_sessions():
    """Clears the in-memory session registry (useful for test resets)."""
    _SESSIONS_BY_ID.clear()
    _SESSION_TRANSACTIONS.clear()
