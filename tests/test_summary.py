"""
Unit tests for SpendGuard Plain-English Decision Summary Generation across all 4 pillars and verdicts.
"""

from datetime import datetime, timezone
import pytest

from data.schema import TransactionRequest, Product
from policy.schema import Mandate
from intent.schema import UserIntent
from policy.authorization import AuthorizationResult
from intent.fidelity import IntentFidelityResult
from evidence.check import EvidenceResult
from decision.engine import BehavioralRiskResult
from decision.summary import build_plain_english_summary


def test_summary_allow_clean_purchase():
    """Validates summary for a clean ALLOW purchase."""
    tx = TransactionRequest(
        id="tx_sum_01",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "Dell", "model": "Inspiron 15 5530"},
        actual_sku="TRAP-ELEC-DELL-5530-CLEAN",
        amount=48990.0,
        category="electronics",
        merchant="Dell Official Store",
        timestamp=datetime.now(timezone.utc),
        scenario_type="clean_baseline",
        expected_decision="ALLOW",
    )
    auth = AuthorizationResult(passed=True, failed_checks=[], is_stale=False)
    intent = IntentFidelityResult(hard_match=True, soft_score=1.0, mismatched_fields=[])
    evidence = EvidenceResult(conflict=False)
    risk = BehavioralRiskResult(score=0.03, top_reasons=[])

    summary = build_plain_english_summary(
        transaction=tx,
        decision="ALLOW",
        decision_reason="allowed: all checks passed, risk score 0.03",
        authorization=auth,
        intent_fidelity=intent,
        evidence=evidence,
        behavioral_risk=risk,
    )

    assert "Approved purchase of Dell Inspiron 15 5530" in summary
    assert "Dell Official Store" in summary
    assert "₹48,990.00" in summary
    assert "passed independent catalog spec verification" in summary
    assert "low behavioral risk" in summary


def test_summary_verify_soft_preference_substitution():
    """Validates summary for a VERIFY hold on soft preference / substitution."""
    tx = TransactionRequest(
        id="tx_sum_02",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "Bose", "model": "QuietComfort 45"},
        actual_sku="TRAP-ELEC-BOSE-QC45-SUBST",
        amount=24900.0,
        category="electronics",
        merchant="Bose Authorized Hub",
        timestamp=datetime.now(timezone.utc),
        scenario_type="near_miss_substitution",
        expected_decision="VERIFY",
    )
    auth = AuthorizationResult(passed=True, failed_checks=[], is_stale=False)
    intent = IntentFidelityResult(
        hard_match=True,
        soft_score=0.0,
        mismatched_fields=["color"],
    )
    evidence = EvidenceResult(conflict=False)
    risk = BehavioralRiskResult(score=0.15, top_reasons=[])

    summary = build_plain_english_summary(
        transaction=tx,
        decision="VERIFY",
        decision_reason="verified: intent soft score 0.00 is below threshold (substitution/preference deviation)",
        authorization=auth,
        intent_fidelity=intent,
        evidence=evidence,
        behavioral_risk=risk,
    )

    assert "Held for human review:" in summary
    assert "Bose QuietComfort 45" in summary
    assert "satisfies core mandatory requirements and budget caps" in summary


def test_summary_block_pillar1_merchant_not_allowed():
    """Validates summary for Pillar 1 Authorization block on merchant."""
    tx = TransactionRequest(
        id="tx_sum_03",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "Apple", "model": "iPhone 15"},
        actual_sku="ELEC-IPHONE-15",
        amount=69900.0,
        category="electronics",
        merchant="UnauthorizedShadyStore",
        timestamp=datetime.now(timezone.utc),
        scenario_type="merchant_trap",
        expected_decision="BLOCK",
    )
    auth = AuthorizationResult(passed=False, failed_checks=["merchant_not_allowed"], is_stale=False)

    summary = build_plain_english_summary(
        transaction=tx,
        decision="BLOCK",
        decision_reason="blocked: authorization failed (merchant_not_allowed)",
        authorization=auth,
        intent_fidelity="skipped",
        evidence="skipped",
        behavioral_risk="skipped",
    )

    assert "Purchase rejected by Pillar 1 (Authorization)" in summary
    assert "UnauthorizedShadyStore" in summary
    assert "approved corporate vendor whitelist" in summary


def test_summary_block_pillar2_intent_mismatch():
    """Validates summary for Pillar 2 Intent Fidelity block on brand/specs."""
    tx = TransactionRequest(
        id="tx_sum_04",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "GenericBrand", "model": "FakeBook"},
        actual_sku="ELEC-FAKE-01",
        amount=45000.0,
        category="electronics",
        merchant="Dell Official Store",
        timestamp=datetime.now(timezone.utc),
        scenario_type="wrong_brand",
        expected_decision="BLOCK",
    )
    intent = IntentFidelityResult(hard_match=False, soft_score=0.0, mismatched_fields=["brand"])

    summary = build_plain_english_summary(
        transaction=tx,
        decision="BLOCK",
        decision_reason="blocked: intent fidelity hard requirement mismatch (brand)",
        authorization=AuthorizationResult(passed=True, failed_checks=[], is_stale=False),
        intent_fidelity=intent,
        evidence="skipped",
        behavioral_risk="skipped",
    )

    assert "Purchase rejected by Pillar 2 (Intent Fidelity)" in summary
    assert "violates hard user constraints" in summary


def test_summary_block_pillar3_evidence_conflict():
    """Validates summary for Pillar 3 Evidence block on hardware spoofing."""
    tx = TransactionRequest(
        id="tx_sum_05",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "Lenovo", "model": "ThinkPad T14 Gen 4"},
        actual_sku="TRAP-ELEC-LENOVO-T14-SPOOF",
        amount=49990.0,
        category="electronics",
        merchant="TechDeals Direct",
        timestamp=datetime.now(timezone.utc),
        scenario_type="spec_spoofing",
        expected_decision="BLOCK",
    )
    evidence = EvidenceResult(
        conflict=True,
        conflicts=[
            {"field": "ram_gb", "claimed": 32, "actual": 8},
            {"field": "storage_gb", "claimed": 1024, "actual": 256},
        ],
        discrepancies=[
            "ram_gb mismatch (claimed '32' vs actual '8')",
            "storage_gb mismatch (claimed '1024' vs actual '256')",
        ],
    )

    summary = build_plain_english_summary(
        transaction=tx,
        decision="BLOCK",
        decision_reason="blocked: evidence conflict on hard requirement (ram_gb, storage_gb)",
        authorization=AuthorizationResult(passed=True, failed_checks=[], is_stale=False),
        intent_fidelity=IntentFidelityResult(hard_match=True, soft_score=1.0, mismatched_fields=[]),
        evidence=evidence,
        behavioral_risk="skipped",
    )

    assert "Purchase rejected by Pillar 3 (Evidence Verification)" in summary
    assert "ram_gb mismatch (claimed '32' vs actual '8')" in summary
    assert "storage_gb mismatch (claimed '1024' vs actual '256')" in summary


def test_summary_block_pillar4_deceptive_split():
    """Validates summary for Pillar 4 Deceptive Split Payment evasion block."""
    tx = TransactionRequest(
        id="tx_sum_06",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "NVIDIA", "model": "GeForce RTX 4060 (Installment Token 1 of 3)"},
        actual_sku="TRAP-ELEC-RTX4060-SPLIT-01",
        amount=9999.0,
        category="electronics",
        merchant="GPU Express Hub",
        timestamp=datetime.now(timezone.utc),
        scenario_type="price_split_bait",
        expected_decision="BLOCK",
    )

    summary = build_plain_english_summary(
        transaction=tx,
        decision="BLOCK",
        decision_reason="blocked: deceptive split-payment installment token pattern detected (fraud limit evasion)",
        authorization=AuthorizationResult(passed=True, failed_checks=[], is_stale=False),
        intent_fidelity=IntentFidelityResult(hard_match=True, soft_score=1.0, mismatched_fields=[]),
        evidence=EvidenceResult(conflict=False),
        behavioral_risk=BehavioralRiskResult(score=0.95, top_reasons=["Split-charge limit evasion"]),
    )

    assert "Purchase rejected by Pillar 4 (Behavioral & Fraud Gate)" in summary
    assert "deceptive split-payment evasion pattern" in summary
    assert "circumvent single-transaction limits using installment tokens" in summary
