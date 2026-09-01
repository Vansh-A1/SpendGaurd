"""
SpendGuard Plain-English Decision Summary Generator.

Generates concise, human-readable, deterministic explanations for every transaction verdict
(ALLOW, VERIFY, BLOCK) across all four pillars without calling an external LLM.
"""

from typing import Any, Dict, List, Optional
import json


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """Helper to retrieve attribute or dictionary key safely."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def build_plain_english_summary(
    transaction: Any,
    decision: str,
    decision_reason: str,
    authorization: Any,
    intent_fidelity: Any,
    evidence: Any,
    behavioral_risk: Any,
    goal_drift: Any = None,
) -> str:
    """
    Constructs a plain-English, one-paragraph summary of the transaction evaluation
    designed for non-technical human operators and LLM agent reasoning.
    """
    merchant = _get_val(transaction, "merchant", "the merchant")
    amount = float(_get_val(transaction, "amount", 0.0))
    sku = _get_val(transaction, "actual_sku", "")
    claimed = _get_val(transaction, "claimed_product", {})
    if isinstance(claimed, str):
        try:
            claimed = json.loads(claimed)
        except Exception:
            claimed = {}
    elif not isinstance(claimed, dict):
        claimed = getattr(claimed, "__dict__", {})

    brand = claimed.get("brand") or _get_val(transaction, "brand", "")
    model = claimed.get("model") or _get_val(transaction, "model", "")
    item_desc = f"{brand} {model}".strip() or sku or "item"

    # =========================================================================
    # 1. ALLOW Summary
    # =========================================================================
    if decision == "ALLOW":
        risk_score = _get_val(behavioral_risk, "score", 0.0)
        return (
            f"Approved purchase of {item_desc} (SKU: {sku}) from {merchant} for ₹{amount:,.2f}. "
            f"The transaction satisfied all corporate policy limits, passed independent catalog spec verification, "
            f"matched the user's requirements, and demonstrated low behavioral risk (score: {risk_score:.2f})."
        )

    # =========================================================================
    # 2. VERIFY Summary (Human Escalation Required)
    # =========================================================================
    if decision == "VERIFY":
        # Check for soft preference / near-miss substitution
        missed_prefs = _get_val(intent_fidelity, "missed_soft_preferences", [])
        is_subst = _get_val(intent_fidelity, "is_substitution", False)
        if missed_prefs or is_subst or "soft" in decision_reason.lower() or "substitution" in decision_reason.lower() or "preference" in decision_reason.lower():
            diff_text = f"on {', '.join(missed_prefs)}" if missed_prefs else "on preferred variant attributes"
            return (
                f"Held for human review: An alternative variant for {item_desc} from {merchant} (₹{amount:,.2f}) was selected "
                f"that differs {diff_text}, but satisfies core mandatory requirements and budget caps. "
                "An operator should confirm whether this substitution is acceptable."
            )

        # Check for elevated behavioral risk
        risk_score = _get_val(behavioral_risk, "score", 0.0)
        top_reasons = _get_val(behavioral_risk, "top_reasons", [])
        if "behavioral" in decision_reason.lower() or "risk" in decision_reason.lower() or risk_score > 0.4:
            reasons_str = "; ".join(top_reasons) if top_reasons else "elevated velocity detected"
            return (
                f"Held for human review: The purchase of {item_desc} from {merchant} for ₹{amount:,.2f} triggered an "
                f"elevated behavioral risk score ({risk_score:.2f}) due to: {reasons_str}. "
                "An operator should verify this purchase is authorized before funds are captured."
            )

        # Check for stale mandate / TTL warning
        if "stale" in decision_reason.lower() or "ttl" in decision_reason.lower() or "mandate" in decision_reason.lower():
            return (
                f"Held for human review: The corporate mandate authorizing purchases for this agent has expired or is nearing expiry. "
                "An operator must confirm renewed authorization before the purchase can proceed."
            )

        # Check for goal drift in multi-item sessions
        if goal_drift and (_get_val(goal_drift, "has_drift", False) or "drift" in decision_reason.lower()):
            reason = _get_val(goal_drift, "reason", "session limits exceeded")
            return (
                f"Held for human review: Multi-item procurement session threshold was reached ({reason}). "
                "An operator should review overall session spend progress."
            )

        # Default fallback VERIFY summary
        return (
            f"Held for human review: Purchase of {item_desc} from {merchant} for ₹{amount:,.2f} requires operator clearance. "
            f"Reason: {decision_reason}."
        )

    # =========================================================================
    # 3. BLOCK Summary (Hard Gate Rejections)
    # =========================================================================
    if decision == "BLOCK":
        reason_lower = decision_reason.lower()

        # Pillar 3: Evidence & Spec Spoofing conflicts
        conflicts = _get_val(evidence, "conflicts", [])
        discrepancies = _get_val(evidence, "discrepancies", [])
        if conflicts or discrepancies or "evidence" in reason_lower:
            if discrepancies:
                disc_text = "; ".join(discrepancies)
            elif conflicts:
                disc_text = "; ".join(f"{c.get('field')} claimed '{c.get('claimed')}' vs actual '{c.get('actual')}'" for c in conflicts)
            else:
                disc_text = "hardware specifications"
            return (
                f"Purchase rejected by Pillar 3 (Evidence Verification): Independent catalog verification detected "
                f"a specification conflict with the seller's claims: {disc_text}."
            )

        # Pillar 4: Deceptive Split Payment & Evasion
        if "split" in reason_lower or "token" in reason_lower or "evasion" in reason_lower:
            return (
                f"Purchase rejected by Pillar 4 (Behavioral & Fraud Gate): This transaction matches a deceptive "
                f"split-payment evasion pattern ('{item_desc}') designed to circumvent single-transaction limits using installment tokens."
            )

        # Pillar 4: Severe Behavioral Risk
        risk_score = _get_val(behavioral_risk, "score", 0.0)
        top_reasons = _get_val(behavioral_risk, "top_reasons", [])
        if "behavioral risk" in reason_lower or risk_score > 0.75:
            reasons_str = "; ".join(top_reasons) if top_reasons else "severe velocity anomaly"
            return (
                f"Purchase rejected by Pillar 4 (Behavioral Risk): The transaction score ({risk_score:.2f}) breached the hard risk ceiling. "
                f"Triggering factors: {reasons_str}."
            )

        # Pillar 1: Authorization failures
        if "merchant_not_allowed" in reason_lower or "merchant" in reason_lower:
            return (
                f"Purchase rejected by Pillar 1 (Authorization): The seller '{merchant}' is not on the approved "
                f"corporate vendor whitelist for this procurement agent."
            )
        if "cap" in reason_lower or "budget" in reason_lower or "amount" in reason_lower:
            return (
                f"Purchase rejected by Pillar 1 (Authorization): The requested amount of ₹{amount:,.2f} exceeds "
                f"the authorized spending cap defined in the corporate mandate."
            )
        if "category_not_allowed" in reason_lower or "category" in reason_lower:
            cat = _get_val(transaction, "category", "specified")
            return (
                f"Purchase rejected by Pillar 1 (Authorization): The category '{cat}' is not authorized for "
                f"this agent's scope."
            )
        if "time_window" in reason_lower:
            return (
                f"Purchase rejected by Pillar 1 (Authorization): The purchase was attempted outside authorized corporate operating hours."
            )
        if "mandate_expired" in reason_lower or "stale" in reason_lower:
            return (
                f"Purchase rejected by Pillar 1 (Authorization): The corporate mandate has expired and cannot authorize new transactions."
            )

        # Pillar 2: Intent Fidelity failures
        hard_mismatches = _get_val(intent_fidelity, "mismatched_fields", []) or _get_val(intent_fidelity, "hard_mismatches", [])
        if hard_mismatches or "intent fidelity" in reason_lower or "intent" in reason_lower:
            fields_str = ", ".join(hard_mismatches) if hard_mismatches else "core requirements"
            return (
                f"Purchase rejected by Pillar 2 (Intent Fidelity): The selected product violates hard user constraints "
                f"({fields_str}) and does not match the requested specifications."
            )

        # Default fallback BLOCK summary
        return (
            f"Purchase of {item_desc} for ₹{amount:,.2f} was rejected by SpendGuard Trust Gateway. "
            f"Reason: {decision_reason}."
        )

    return f"Transaction {sku} resolved with verdict {decision}: {decision_reason}."
