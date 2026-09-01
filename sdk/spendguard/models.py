from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Literal, Union
from pydantic import BaseModel, Field


class ClaimedProduct(BaseModel):
    sku: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    specs: Dict[str, Any] = Field(default_factory=dict)


class TransactionRequest(BaseModel):
    id: str
    agent_id: str
    mandate_id: str
    user_intent_id: str
    claimed_product: Union[Dict[str, Any], ClaimedProduct]
    actual_sku: str
    amount: float
    category: str
    merchant: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scenario_type: str = "clean_baseline"
    expected_decision: Literal["ALLOW", "VERIFY", "BLOCK"] = "ALLOW"
    session_id: Optional[str] = None
    intent_version: int = 1


class AuthorizationResultModel(BaseModel):
    passed: bool
    failed_checks: List[str] = Field(default_factory=list)
    is_stale: bool = False


class IntentFidelityResultModel(BaseModel):
    passed: bool
    hard_match: bool = True
    hard_mismatches: List[str] = Field(default_factory=list)
    soft_score: float = 1.0
    is_substitution: bool = False
    missed_soft_preferences: List[str] = Field(default_factory=list)


class BehavioralRiskResultModel(BaseModel):
    score: float
    top_reasons: List[str] = Field(default_factory=list)


class EvidenceResultModel(BaseModel):
    conflict: bool = False
    unverifiable: bool = False
    discrepancies: List[str] = Field(default_factory=list)


class GoalDriftResultModel(BaseModel):
    has_drift: bool = False
    reason: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class DecisionReceipt(BaseModel):
    transaction_id: str
    decision: Literal["ALLOW", "VERIFY", "BLOCK"]
    decision_reason: str
    summary: Optional[str] = None
    authorization: Union[AuthorizationResultModel, Dict[str, Any], Literal["skipped"]] = "skipped"
    intent_fidelity: Union[IntentFidelityResultModel, Dict[str, Any], Literal["skipped"]] = "skipped"
    behavioral_risk: Union[BehavioralRiskResultModel, Dict[str, Any], Literal["skipped"]] = "skipped"
    evidence: Union[EvidenceResultModel, Dict[str, Any], Literal["skipped"]] = "skipped"
    goal_drift: Optional[Union[GoalDriftResultModel, Dict[str, Any], Literal["skipped"], None]] = None
    provenance_trail: List[Dict[str, Any]] = Field(default_factory=list)
    trust_snapshot: Optional[Dict[str, Any]] = None
    payment_hold_id: Optional[str] = None
    payment_hold_status: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    payment_error: Optional[str] = None

    @property
    def is_allowed(self) -> bool:
        return self.decision == "ALLOW"

    @property
    def is_blocked(self) -> bool:
        return self.decision == "BLOCK"

    @property
    def is_verification_required(self) -> bool:
        return self.decision == "VERIFY"
