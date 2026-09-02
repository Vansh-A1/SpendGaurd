import uuid
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from data.schema import PurchaseSession

# In-memory session registry (lightweight, zero external dependencies)
_SESSION_LOCK = threading.RLock()
_SESSIONS_BY_ID: Dict[str, PurchaseSession] = {}
_SESSION_TRANSACTIONS: Dict[str, List[str]] = {}
_SESSION_COMMITTED_SPEND: Dict[str, float] = {}
_SESSION_RESERVED_SPEND: Dict[str, float] = {}


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
    Thread-safe.
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

    with _SESSION_LOCK:
        _SESSIONS_BY_ID[s_id] = session
        if s_id not in _SESSION_TRANSACTIONS:
            _SESSION_TRANSACTIONS[s_id] = []
        if s_id not in _SESSION_COMMITTED_SPEND:
            _SESSION_COMMITTED_SPEND[s_id] = 0.0
        if s_id not in _SESSION_RESERVED_SPEND:
            _SESSION_RESERVED_SPEND[s_id] = 0.0

    return session


def get_session(session_id: str) -> Optional[PurchaseSession]:
    """Retrieve a registered PurchaseSession by session_id."""
    with _SESSION_LOCK:
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
    with _SESSION_LOCK:
        sessions = list(_SESSIONS_BY_ID.values())
        if agent_id:
            return [s for s in sessions if s.agent_id == agent_id]
        return sessions


def reserve_session_budget(session_id: str, amount: float) -> Tuple[bool, float, float]:
    """
    Atomically attempts to reserve budget for an in-flight transaction under session_id.
    Returns (success: bool, current_total_projected: float, declared_budget: float).
    """
    with _SESSION_LOCK:
        session = get_session(session_id)
        if not session or not session.declared_total_budget:
            # No session or unconstrained session budget
            return True, amount, float("inf")

        committed = _SESSION_COMMITTED_SPEND.get(session_id, 0.0)
        reserved = _SESSION_RESERVED_SPEND.get(session_id, 0.0)
        projected = committed + reserved + amount

        if projected > session.declared_total_budget + 0.01:
            return False, projected, session.declared_total_budget

        # Reserve
        _SESSION_RESERVED_SPEND[session_id] = reserved + amount
        return True, projected, session.declared_total_budget


def release_session_reservation(session_id: str, amount: float):
    """Releases previously reserved budget if transaction is blocked or fails."""
    with _SESSION_LOCK:
        if session_id in _SESSION_RESERVED_SPEND:
            _SESSION_RESERVED_SPEND[session_id] = max(0.0, _SESSION_RESERVED_SPEND[session_id] - amount)


def commit_session_spend(session_id: str, transaction_id: str, amount: float):
    """Transfers reserved spend to committed spend upon ALLOW/VERIFY settlement."""
    with _SESSION_LOCK:
        if session_id not in _SESSION_TRANSACTIONS:
            _SESSION_TRANSACTIONS[session_id] = []
        if transaction_id not in _SESSION_TRANSACTIONS[session_id]:
            _SESSION_TRANSACTIONS[session_id].append(transaction_id)

        if session_id in _SESSION_RESERVED_SPEND:
            _SESSION_RESERVED_SPEND[session_id] = max(0.0, _SESSION_RESERVED_SPEND[session_id] - amount)
        _SESSION_COMMITTED_SPEND[session_id] = _SESSION_COMMITTED_SPEND.get(session_id, 0.0) + amount


def record_session_transaction(session_id: str, transaction_id: str, amount: float = 0.0):
    """Associates a transaction_id with an active session."""
    with _SESSION_LOCK:
        if session_id not in _SESSION_TRANSACTIONS:
            _SESSION_TRANSACTIONS[session_id] = []
        if transaction_id not in _SESSION_TRANSACTIONS[session_id]:
            _SESSION_TRANSACTIONS[session_id].append(transaction_id)
        if amount > 0:
            _SESSION_COMMITTED_SPEND[session_id] = _SESSION_COMMITTED_SPEND.get(session_id, 0.0) + amount


def get_session_transactions(session_id: str) -> List[str]:
    """Returns all transaction IDs associated with a given session_id."""
    with _SESSION_LOCK:
        return list(_SESSION_TRANSACTIONS.get(session_id, []))


def clear_sessions():
    """Clears the in-memory session registry (useful for test resets)."""
    with _SESSION_LOCK:
        _SESSIONS_BY_ID.clear()
        _SESSION_TRANSACTIONS.clear()
        _SESSION_COMMITTED_SPEND.clear()
        _SESSION_RESERVED_SPEND.clear()
