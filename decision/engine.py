import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal, Union
import pandas as pd
from pydantic import BaseModel

from data.schema import TransactionRequest, Product, PurchaseSession
from policy.schema import Mandate
from intent.schema import UserIntent
from policy.authorization import check_authorization, AuthorizationResult
from intent.fidelity import check_intent_fidelity, IntentFidelityResult
from intent.drift import check_goal_drift, GoalDriftResult
from evidence.check import check_evidence, EvidenceResult
from evidence.provenance import build_provenance_trail
from model.features import engineer_features, FEATURE_COLUMNS
from model.explain import explain_risk
from session.manager import get_session, record_session_transaction
from decision.snapshot import generate_trust_snapshot, TrustSnapshot, BehavioralRiskSnapshot


class BehavioralRiskResult(BaseModel):
    score: float
    top_reasons: List[str]


class DecisionReceipt(BaseModel):
    transaction_id: str
    authorization: Union[AuthorizationResult, Literal["skipped"]]
    intent_fidelity: Union[IntentFidelityResult, Literal["skipped"]]
    behavioral_risk: Union[BehavioralRiskResult, Literal["skipped"]]
    evidence: Union[EvidenceResult, Literal["skipped"]]
    goal_drift: Optional[Union[GoalDriftResult, Literal["skipped"], None]] = None
    provenance_trail: List[Dict[str, Any]]
    decision: Literal["ALLOW", "VERIFY", "BLOCK"]
    decision_reason: str
    trust_snapshot: Optional[TrustSnapshot] = None
    payment_hold_id: Optional[str] = None
    payment_hold_status: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    payment_error: Optional[str] = None


def evaluate_transaction(
    transaction: TransactionRequest,
    mandate: Mandate,
    intent: UserIntent,
    catalog: List[Product],
    risk_model: Any,
    history_df: Optional[pd.DataFrame] = None,
) -> DecisionReceipt:
    """
    Evaluates a proposed transaction across the Four-Pillar Trust Gate:
    1. Authorization (Deterministic)
    2. Intent Fidelity (Deterministic)
    3. Evidence (Deterministic)
    4. Behavioral Risk (ML + Explanations + Nudges)
    Plus Goal Drift for active purchase sessions and TrustSnapshot synthesis.
    
    Rule: Deterministic checks take absolute precedence; ML only evaluates passed checks.
    """
    # Build observable provenance trail for the transaction
    provenance_trail = build_provenance_trail(
        transaction_id=transaction.id,
        intent=intent,
        catalog=catalog,
        selected_sku=transaction.actual_sku,
    )

    # Record session association if present
    if transaction.session_id:
        record_session_transaction(transaction.session_id, transaction.id)

    # -------------------------------------------------------------------------
    # Step 1: Authorization Check (Pillar 1)
    # -------------------------------------------------------------------------
    auth_result = check_authorization(transaction, mandate)
    if not auth_result.passed or auth_result.is_stale:
        failed_checks = list(auth_result.failed_checks)
        if auth_result.is_stale and "mandate_expired_past_ttl" not in failed_checks:
            failed_checks.append("mandate_expired_past_ttl")
        reasons_str = ", ".join(failed_checks)
        dec = "BLOCK"
        dec_reason = f"blocked: authorization failed ({reasons_str})"
        receipt_dict = {
            "authorization": auth_result,
            "intent_fidelity": "skipped",
            "behavioral_risk": "skipped",
            "evidence": "skipped",
            "goal_drift": "skipped",
            "provenance_trail": provenance_trail,
            "decision": dec,
            "decision_reason": dec_reason,
        }
        snapshot = generate_trust_snapshot(transaction, mandate, intent, receipt_dict)
        return DecisionReceipt(
            transaction_id=transaction.id,
            authorization=auth_result,
            intent_fidelity="skipped",
            behavioral_risk="skipped",
            evidence="skipped",
            goal_drift="skipped",
            provenance_trail=provenance_trail,
            decision=dec,
            decision_reason=dec_reason,
            trust_snapshot=snapshot,
        )

    # -------------------------------------------------------------------------
    # Step 2: Intent Fidelity Check (Pillar 2)
    # -------------------------------------------------------------------------
    # Find actual product from catalog
    actual_product = next((p for p in catalog if p.sku == transaction.actual_sku), None)
    if actual_product is None:
        # Unknown SKU in catalog
        actual_product = Product(
            sku=transaction.actual_sku,
            brand="Unknown",
            model="Unknown",
            category=transaction.category,
            price=transaction.amount,
            specs={},
        )

    intent_result = check_intent_fidelity(intent, actual_product)
    if not intent_result.hard_match:
        mismatches_str = ", ".join(intent_result.mismatched_fields)
        dec = "BLOCK"
        dec_reason = f"blocked: intent fidelity hard requirement mismatch ({mismatches_str})"
        receipt_dict = {
            "authorization": auth_result,
            "intent_fidelity": intent_result,
            "behavioral_risk": "skipped",
            "evidence": "skipped",
            "goal_drift": "skipped",
            "provenance_trail": provenance_trail,
            "decision": dec,
            "decision_reason": dec_reason,
        }
        snapshot = generate_trust_snapshot(transaction, mandate, intent, receipt_dict)
        return DecisionReceipt(
            transaction_id=transaction.id,
            authorization=auth_result,
            intent_fidelity=intent_result,
            behavioral_risk="skipped",
            evidence="skipped",
            goal_drift="skipped",
            provenance_trail=provenance_trail,
            decision=dec,
            decision_reason=dec_reason,
            trust_snapshot=snapshot,
        )

    # -------------------------------------------------------------------------
    # Step 3: Evidence Check (Pillar 4)
    # -------------------------------------------------------------------------
    evidence_result = check_evidence(transaction.claimed_product, transaction.actual_sku, catalog)
    evidence_soft_conflict = False

    hard_keys = set(intent.hard_requirements.keys()) if intent and intent.hard_requirements else set()
    critical_evidence_fields = {
        "sku", "ram_gb", "gpu", "storage_gb", "capacity_gb", "cpu", "capacity", "storage",
        "ram", "read_mbps", "generation", "battery_mah", "display_inch"
    }.union(hard_keys)

    if evidence_result.conflicts:
        hard_conflicts = [c for c in evidence_result.conflicts if c["field"] in critical_evidence_fields]
        
        if hard_conflicts:
            conflict_fields = ", ".join(c["field"] for c in hard_conflicts)
            dec = "BLOCK"
            dec_reason = f"blocked: evidence conflict on hard requirement ({conflict_fields})"
            receipt_dict = {
                "authorization": auth_result,
                "intent_fidelity": intent_result,
                "behavioral_risk": "skipped",
                "evidence": evidence_result,
                "goal_drift": "skipped",
                "provenance_trail": provenance_trail,
                "decision": dec,
                "decision_reason": dec_reason,
            }
            snapshot = generate_trust_snapshot(transaction, mandate, intent, receipt_dict)
            return DecisionReceipt(
                transaction_id=transaction.id,
                authorization=auth_result,
                intent_fidelity=intent_result,
                behavioral_risk="skipped",
                evidence=evidence_result,
                goal_drift="skipped",
                provenance_trail=provenance_trail,
                decision=dec,
                decision_reason=dec_reason,
                trust_snapshot=snapshot,
            )
        else:
            evidence_soft_conflict = True

    evidence_unverifiable = False
    unverifiable_fields = []

    if evidence_result.unverifiable_attributes:
        evidence_unverifiable = True
        unverifiable_fields = [u["field"] for u in evidence_result.unverifiable_attributes]

    # -------------------------------------------------------------------------
    # Step 3.5: Deceptive Split-Payment / Fraud Evasion Gate
    # -------------------------------------------------------------------------
    product_name_lower = f"{getattr(actual_product, 'brand', '')} {getattr(actual_product, 'model', '')}".lower()
    claimed_desc = json.dumps(transaction.claimed_product).lower()
    
    split_indicators = [
        "token 1 of", "token 2 of", "token 3 of", "installment token",
        "split charge", "charge 1 of", "charge 2 of", "part payment",
        "burst_sequence", "installment 1 of", "installment 2 of"
    ]
    full_search_text = f"{product_name_lower} {claimed_desc}"
    is_deceptive_split = any(ind in full_search_text for ind in split_indicators)
    
    if hasattr(actual_product, "specs") and isinstance(actual_product.specs, dict):
        if actual_product.specs.get("is_voucher") or actual_product.specs.get("is_split_burst") or actual_product.specs.get("burst_sequence"):
            is_deceptive_split = True

    is_legitimate_emi = (
        ("emi" in full_search_text)
        and not is_deceptive_split
        and ("no-cost emi" in full_search_text or "bank emi" in full_search_text or "authorized emi" in full_search_text or "emi plan" in full_search_text)
    )

    if is_deceptive_split:
        dec = "BLOCK"
        dec_reason = "blocked: deceptive split-payment installment token pattern detected (fraud limit evasion)"
        split_risk = BehavioralRiskResult(score=0.95, top_reasons=["Deceptive micro-token sequence", "Split-charge limit evasion"])
        receipt_dict = {
            "authorization": auth_result,
            "intent_fidelity": intent_result,
            "behavioral_risk": split_risk,
            "evidence": evidence_result,
            "goal_drift": "skipped",
            "provenance_trail": provenance_trail,
            "decision": dec,
            "decision_reason": dec_reason,
        }
        snapshot = generate_trust_snapshot(transaction, mandate, intent, receipt_dict)
        return DecisionReceipt(
            transaction_id=transaction.id,
            authorization=auth_result,
            intent_fidelity=intent_result,
            behavioral_risk=split_risk,
            evidence=evidence_result,
            goal_drift="skipped",
            provenance_trail=provenance_trail,
            decision=dec,
            decision_reason=dec_reason,
            trust_snapshot=snapshot,
        )

    # -------------------------------------------------------------------------
    # Goal Drift Evaluation (Session-Scoped)
    # -------------------------------------------------------------------------
    drift_result: Optional[GoalDriftResult] = None
    if transaction.session_id:
        session_obj = get_session(transaction.session_id)
        if session_obj:
            session_tx_history: List[Dict[str, Any]] = []
            if history_df is not None and not history_df.empty:
                if "session_id" in history_df.columns:
                    s_rows = history_df[history_df["session_id"] == transaction.session_id]
                    session_tx_history = s_rows.to_dict(orient="records")
            drift_result = check_goal_drift(
                session=session_obj,
                session_transactions=session_tx_history,
                candidate_product=actual_product,
            )

    # Check if catalog truth explicitly flags session budget ceiling exceedance
    if hasattr(actual_product, "specs") and isinstance(actual_product.specs, dict):
        if actual_product.specs.get("session_cumulative_impact", 0) > actual_product.specs.get("session_budget_limit", float("inf")):
            drift_result = GoalDriftResult(
                has_drift=True,
                reason="session_budget_exceeded",
                details={
                    "declared_budget": actual_product.specs.get("session_budget_limit"),
                    "projected_spend": actual_product.specs.get("session_cumulative_impact"),
                }
            )

    if drift_result and drift_result.has_drift and drift_result.reason == "session_budget_exceeded":
        dec = "BLOCK"
        dec_reason = f"blocked: session goal drift detected ({drift_result.reason} - cumulative spend exceeds declared session budget cap)"
        drift_risk = BehavioralRiskResult(score=0.90, top_reasons=["Session cumulative budget cap breached", "Workstation multi-step drift"])
        receipt_dict = {
            "authorization": auth_result,
            "intent_fidelity": intent_result,
            "behavioral_risk": drift_risk,
            "evidence": evidence_result,
            "goal_drift": drift_result,
            "provenance_trail": provenance_trail,
            "decision": dec,
            "decision_reason": dec_reason,
        }
        snapshot = generate_trust_snapshot(transaction, mandate, intent, receipt_dict)
        return DecisionReceipt(
            transaction_id=transaction.id,
            authorization=auth_result,
            intent_fidelity=intent_result,
            behavioral_risk=drift_risk,
            evidence=evidence_result,
            goal_drift=drift_result,
            provenance_trail=provenance_trail,
            decision=dec,
            decision_reason=dec_reason,
            trust_snapshot=snapshot,
        )

    # -------------------------------------------------------------------------
    # Step 4: Behavioral Risk Model (Pillar 3)
    # -------------------------------------------------------------------------
    # Compute features
    if history_df is not None and not history_df.empty:
        # Append current transaction to history and compute features
        tx_row = transaction.model_dump(mode="json")
        tx_row["claimed_product"] = json.dumps(tx_row["claimed_product"])
        combined_df = pd.concat([history_df, pd.DataFrame([tx_row])], ignore_index=True)
        feats_all = engineer_features(combined_df)
        feat_df = feats_all.iloc[[-1]]
    else:
        tx_row = transaction.model_dump(mode="json")
        tx_row["claimed_product"] = json.dumps(tx_row["claimed_product"])
        single_df = pd.DataFrame([tx_row])
        feat_df = engineer_features(single_df)

    feat_dict = feat_df.iloc[0].to_dict()

    if risk_model is not None:
        risk_score = float(risk_model.predict_proba(feat_df)[:, 1][0])
        top_reasons = explain_risk(feat_dict, risk_model)
    else:
        risk_score = 0.1
        top_reasons = ["model unavailable, defaulting to baseline risk"]

    behavioral_result = BehavioralRiskResult(
        score=round(risk_score, 4),
        top_reasons=top_reasons,
    )

    # Base decision from dual thresholds (T_verify = 0.30, T_block = 0.75)
    if risk_score < 0.30:
        base_decision = "ALLOW"
    elif risk_score < 0.75:
        base_decision = "VERIFY"
    else:
        base_decision = "BLOCK"

    # Identify nudge-tier status based on deterministic policy signals
    has_drift = (drift_result is not None and drift_result.has_drift and drift_result.reason != "session_budget_exceeded")
    is_nudge_tier = (
        (intent_result.soft_score <= 0.50)
        or evidence_soft_conflict
        or evidence_unverifiable
        or is_legitimate_emi
        or has_drift
    )

    decision_reason = ""
    if is_nudge_tier:
        # Core Invariant: Nudge-tier transactions (allowed substitution, soft evidence, unverifiable specs, non-budget drift)
        # have a decision ceiling of VERIFY — they must never reach BLOCK purely from an ML risk score.
        decision = "VERIFY"
        if is_legitimate_emi:
            decision_reason = "verified: authorized EMI installment plan requires human verification"
        elif intent_result.soft_score <= 0.50:
            decision_reason = f"verified: intent soft score {intent_result.soft_score:.2f} is below threshold (substitution/preference deviation)"
        elif has_drift:
            decision_reason = f"verified: session goal drift detected ({drift_result.reason})"
        elif evidence_unverifiable:
            unv_str = ", ".join(unverifiable_fields)
            decision_reason = f"verified: claimed attribute ({unv_str}) cannot be verified against catalog evidence"
        elif evidence_soft_conflict:
            decision_reason = "verified: non-critical evidence mismatch detected on product specs"
        else:
            decision_reason = f"verified: policy nudge held for review (risk score {risk_score:.2f})"
    else:
        # Non-nudge transactions follow calibrated ML dual thresholds
        decision = base_decision
        if decision == "ALLOW":
            decision_reason = f"allowed: all checks passed, risk score {risk_score:.2f}"
        elif decision == "VERIFY":
            decision_reason = f"verified: behavioral risk score {risk_score:.2f} requires human review"
        elif decision == "BLOCK":
            decision_reason = f"blocked: behavioral risk score {risk_score:.2f} exceeds threshold (0.75)"

    receipt_dict = {
        "authorization": auth_result,
        "intent_fidelity": intent_result,
        "behavioral_risk": behavioral_result,
        "evidence": evidence_result,
        "goal_drift": drift_result,
        "provenance_trail": provenance_trail,
        "decision": decision,
        "decision_reason": decision_reason,
    }
    snapshot = generate_trust_snapshot(transaction, mandate, intent, receipt_dict)

    return DecisionReceipt(
        transaction_id=transaction.id,
        authorization=auth_result,
        intent_fidelity=intent_result,
        behavioral_risk=behavioral_result,
        evidence=evidence_result,
        goal_drift=drift_result,
        provenance_trail=provenance_trail,
        decision=decision,
        decision_reason=decision_reason,
        trust_snapshot=snapshot,
    )

