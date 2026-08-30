import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field

from data.schema import TransactionRequest, Product
from policy.schema import Mandate
from intent.schema import UserIntent
from policy.authorization import AuthorizationResult
from intent.fidelity import IntentFidelityResult
from evidence.check import EvidenceResult
from intent.drift import GoalDriftResult


class BehavioralRiskSnapshot(BaseModel):
    score: float
    top_reasons: List[str]


class TrustSnapshot(BaseModel):
    trust_snapshot_id: str
    intent_id: str
    intent_version: int = 1
    mandate_id: str
    mandate_version: int = 1
    agent_id: str
    purchase_session_id: Optional[str] = None
    selected_sku: str
    amount: float
    authorization_result: Union[AuthorizationResult, Literal["skipped"], Dict[str, Any]]
    intent_fidelity: Union[IntentFidelityResult, Literal["skipped"], Dict[str, Any]]
    evidence_result: Union[EvidenceResult, Literal["skipped"], Dict[str, Any]]
    behavioral_risk: Union[BehavioralRiskSnapshot, Literal["skipped"], Dict[str, Any]]
    provenance_reference: Optional[List[Dict[str, Any]]] = None
    goal_drift_result: Optional[Union[GoalDriftResult, Literal["skipped"], Dict[str, Any]]] = None
    decision: Literal["ALLOW", "VERIFY", "BLOCK"]
    decision_reason: str
    decision_timestamp: datetime


def generate_trust_snapshot(
    transaction: TransactionRequest,
    mandate: Mandate,
    intent: UserIntent,
    receipt_data: Dict[str, Any],
    timestamp: Optional[datetime] = None,
) -> TrustSnapshot:
    """
    Constructs a comprehensive, self-contained TrustSnapshot artifact summarizing
    all four-pillar evaluations, provenance chain, and final decision state.
    """
    snap_id = f"snap_{transaction.id}_{uuid.uuid4().hex[:8]}"
    now = timestamp or datetime.now(timezone.utc)

    # Format behavioral risk
    b_risk = receipt_data.get("behavioral_risk", "skipped")
    if b_risk != "skipped" and not isinstance(b_risk, (dict, BehavioralRiskSnapshot)):
        if hasattr(b_risk, "score") and hasattr(b_risk, "top_reasons"):
            b_risk = BehavioralRiskSnapshot(score=b_risk.score, top_reasons=b_risk.top_reasons)

    return TrustSnapshot(
        trust_snapshot_id=snap_id,
        intent_id=intent.id if intent else transaction.user_intent_id,
        intent_version=getattr(intent, "intent_version", transaction.intent_version),
        mandate_id=mandate.id if mandate else transaction.mandate_id,
        mandate_version=getattr(mandate, "version", 1),
        agent_id=transaction.agent_id,
        purchase_session_id=transaction.session_id,
        selected_sku=transaction.actual_sku,
        amount=float(transaction.amount),
        authorization_result=receipt_data.get("authorization", "skipped"),
        intent_fidelity=receipt_data.get("intent_fidelity", "skipped"),
        evidence_result=receipt_data.get("evidence", "skipped"),
        behavioral_risk=b_risk,
        provenance_reference=receipt_data.get("provenance_trail", []),
        goal_drift_result=receipt_data.get("goal_drift"),
        decision=receipt_data["decision"],
        decision_reason=receipt_data["decision_reason"],
        decision_timestamp=now,
    )
