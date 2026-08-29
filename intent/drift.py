from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from data.schema import Product, PurchaseSession


class GoalDriftResult(BaseModel):
    has_drift: bool
    reason: Optional[str] = None
    details: Dict[str, Any] = {}


def check_goal_drift(
    session: PurchaseSession,
    session_transactions: List[Dict[str, Any]],
    candidate_product: Optional[Product] = None,
) -> GoalDriftResult:
    """
    Evaluates session-level goal drift across an agent's multi-step purchase workflow:
    1. Declared Item Count: flags drift if session exceeds declared item limit.
    2. Session Budget Cap: flags drift if projected cumulative spend exceeds declared session budget.
    3. Excessive Retries: flags drift on repeated blocked/failed purchase attempts (>= 3).
    4. Repeated Substitutions: flags drift on repeated candidate substitutions (>= 2).
    """
    completed_txs = [tx for tx in session_transactions if tx.get("decision") in ("ALLOW", "VERIFY")]

    # 1. Declared Item Count Check
    if session.declared_item_count and len(completed_txs) >= session.declared_item_count:
        return GoalDriftResult(
            has_drift=True,
            reason="declared_item_count_exceeded",
            details={
                "declared_count": session.declared_item_count,
                "completed_count": len(completed_txs),
            },
        )

    # 2. Cumulative Session Budget Check
    if session.declared_total_budget:
        current_spend = sum(float(tx.get("amount", 0.0)) for tx in completed_txs)
        candidate_amount = candidate_product.price if candidate_product else 0.0
        if (current_spend + candidate_amount) > float(session.declared_total_budget):
            return GoalDriftResult(
                has_drift=True,
                reason="session_budget_exceeded",
                details={
                    "declared_budget": session.declared_total_budget,
                    "projected_spend": current_spend + candidate_amount,
                },
            )

    # 3. Excessive Retries / Failures Check
    blocked_count = sum(1 for tx in session_transactions if tx.get("decision") == "BLOCK")
    if blocked_count >= 3:
        return GoalDriftResult(
            has_drift=True,
            reason="excessive_session_retries",
            details={"blocked_count": blocked_count},
        )

    # 4. Repeated Substitutions Check
    substitution_count = sum(
        1 for tx in session_transactions
        if "substitution" in str(tx.get("decision_reason", "")).lower()
        or tx.get("scenario_type") == "substitution"
    )
    if substitution_count >= 2:
        return GoalDriftResult(
            has_drift=True,
            reason="repeated_session_substitutions",
            details={"substitution_count": substitution_count},
        )

    return GoalDriftResult(
        has_drift=False,
        reason=None,
        details={"completed_count": len(completed_txs)},
    )
