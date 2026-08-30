import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
import numpy as np

from data.schema import TransactionRequest, Product
from policy.schema import Mandate
from intent.schema import UserIntent
from policy.authorization import AuthorizationResult
from intent.fidelity import IntentFidelityResult
from evidence.check import EvidenceResult
from decision.engine import evaluate_transaction, DecisionReceipt


def test_dual_threshold_boundaries():
    mandate = Mandate(
        id="mandate_thresh",
        agent_id="agent_shopping_01",
        per_transaction_cap=50000.0,
        categories=["electronics"],
        merchants=["Amazon"],
        time_window_start="00:00",
        time_window_end="23:59",
        issued_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=3600000,
    )
    intent = UserIntent(
        id="intent_thresh",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5"},
        soft_preferences={"color": "black"},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    product = Product(
        sku="ELEC-SONY-WH1000XM5-BLK",
        brand="Sony",
        model="WH-1000XM5",
        category="electronics",
        price=29990.0,
        specs={"color": "black"},
    )
    tx = TransactionRequest(
        id="tx_thresh_test",
        agent_id="agent_shopping_01",
        mandate_id="mandate_thresh",
        user_intent_id="intent_thresh",
        claimed_product={"brand": "Sony", "model": "WH-1000XM5"},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=29990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
        scenario_type="legitimate_unusual",
        expected_decision="ALLOW",
    )

    # Mock Model returning specific risk scores
    def make_mock_model(score: float):
        mock = MagicMock()
        mock.predict_proba.return_value = np.array([[1.0 - score, score]])
        mock.feature_importances_ = np.ones(11)
        return mock

    # 1. Score < 0.30 -> ALLOW
    res_allow = evaluate_transaction(tx, mandate, intent, [product], make_mock_model(0.15))
    assert res_allow.decision == "ALLOW"
    assert "allowed" in res_allow.decision_reason

    # 2. 0.30 <= Score < 0.75 -> VERIFY
    res_verify = evaluate_transaction(tx, mandate, intent, [product], make_mock_model(0.55))
    assert res_verify.decision == "VERIFY"
    assert "requires human review" in res_verify.decision_reason

    # 3. Score >= 0.75 -> BLOCK
    res_block = evaluate_transaction(tx, mandate, intent, [product], make_mock_model(0.85))
    assert res_block.decision == "BLOCK"
    assert "exceeds threshold" in res_block.decision_reason


def test_nudge_ceiling_invariant():
    """
    CRITICAL INVARIANT TEST:
    A nudge-tier transaction (e.g. allowed substitution with soft preference score <= 0.50)
    with an artificially elevated ML risk score (e.g. 0.95) must be capped at VERIFY, never BLOCK.
    """
    mandate = Mandate(
        id="mandate_nudge",
        agent_id="agent_shopping_01",
        per_transaction_cap=50000.0,
        categories=["electronics"],
        merchants=["Amazon"],
        time_window_start="00:00",
        time_window_end="23:59",
        issued_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=3600000,
    )
    # Intent allows substitution, but product has lower soft preference score (0.0)
    intent = UserIntent(
        id="intent_nudge",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony"},
        soft_preferences={"color": "white", "anc": True},
        substitution_allowed=True,
        created_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    product = Product(
        sku="ELEC-SONY-WH1000XM4-BLK",
        brand="Sony",
        model="WH-1000XM4",
        category="electronics",
        price=24990.0,
        specs={"color": "black", "anc": False}, # Soft score = 0.0
    )
    tx = TransactionRequest(
        id="tx_nudge_ceiling",
        agent_id="agent_shopping_01",
        mandate_id="mandate_nudge",
        user_intent_id="intent_nudge",
        claimed_product={"brand": "Sony", "model": "WH-1000XM4"},
        actual_sku="ELEC-SONY-WH1000XM4-BLK",
        amount=24990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
        scenario_type="substitution",
        expected_decision="VERIFY",
    )

    # Mock Model predicting extreme risk (0.95)
    mock_extreme_risk = MagicMock()
    mock_extreme_risk.predict_proba.return_value = np.array([[0.05, 0.95]])
    mock_extreme_risk.feature_importances_ = np.ones(11)

    receipt = evaluate_transaction(tx, mandate, intent, [product], mock_extreme_risk)
    # Must resolve to VERIFY due to the nudge ceiling
    assert receipt.decision == "VERIFY"
    assert "below threshold" in receipt.decision_reason


def test_stale_mandate_nudge_ceiling():
    """Stale mandate with extreme ML risk score must still be capped at VERIFY."""
    expired_issued = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    mandate = Mandate(
        id="mandate_stale",
        agent_id="agent_shopping_01",
        per_transaction_cap=50000.0,
        categories=["electronics"],
        merchants=["Amazon"],
        time_window_start="00:00",
        time_window_end="23:59",
        issued_at=expired_issued,
        ttl_seconds=3600, # Expired
    )
    intent = UserIntent(
        id="intent_stale",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5"},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    )
    product = Product(
        sku="ELEC-SONY-WH1000XM5-BLK",
        brand="Sony",
        model="WH-1000XM5",
        category="electronics",
        price=29990.0,
        specs={"color": "black"},
    )
    tx = TransactionRequest(
        id="tx_stale_ceiling",
        agent_id="agent_shopping_01",
        mandate_id="mandate_stale",
        user_intent_id="intent_stale",
        claimed_product={"brand": "Sony", "model": "WH-1000XM5"},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=29990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
        scenario_type="stale_mandate",
        expected_decision="VERIFY",
    )

    mock_extreme_risk = MagicMock()
    mock_extreme_risk.predict_proba.return_value = np.array([[0.10, 0.90]])
    mock_extreme_risk.feature_importances_ = np.ones(11)

    receipt = evaluate_transaction(tx, mandate, intent, [product], mock_extreme_risk)
    assert receipt.decision == "VERIFY"
    assert "stale" in receipt.decision_reason
