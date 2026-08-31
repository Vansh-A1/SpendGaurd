import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd

from data.schema import TransactionRequest, Product, PurchaseSession
from policy.schema import Mandate
from intent.schema import UserIntent
from data.catalog import get_catalog
from decision.engine import evaluate_transaction
from session.manager import create_session, clear_sessions, get_session
from decision.snapshot import TrustSnapshot, generate_trust_snapshot
from api.db import (
    init_db,
    save_transaction_evaluation,
    get_transaction_receipt,
    get_trust_snapshot,
    get_transactions,
)
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture(autouse=True)
def clean_state():
    clear_sessions()
    yield
    clear_sessions()


@pytest.fixture
def catalog():
    return get_catalog()


@pytest.fixture
def mandates():
    with open(Path(__file__).resolve().parent.parent / "data" / "mandates.json") as f:
        data = json.load(f)
        return {m["id"]: Mandate(**m) for m in data}


@pytest.fixture
def client():
    return TestClient(app)


# -----------------------------------------------------------------------------
# TASK 12 TESTS: Goal Drift Detection in Decision Engine
# -----------------------------------------------------------------------------
def test_goal_drift_single_item_count_exceeded_nudge_verify(catalog, mandates):
    """
    Scenario 1: Agent created a session declaring declared_item_count = 1.
    When a second transaction arrives within the session, check_goal_drift flags
    declared_item_count_exceeded, which routes to VERIFY under the nudge ceiling.
    """
    session = create_session(
        session_id="sess_drift_count_test",
        intent_id="intent_drift_1",
        agent_id="agent_shopping_01",
        declared_item_count=1,
        declared_total_budget=50000.0,
    )

    mandate = mandates["mandate_shop_01"]
    intent = UserIntent(
        id="intent_drift_1",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-CH720N"},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    # History contains 1 completed prior transaction in this session
    history_rows = [{
        "id": "tx_prior_01",
        "agent_id": "agent_shopping_01",
        "mandate_id": mandate.id,
        "user_intent_id": intent.id,
        "claimed_product": json.dumps({"brand": "Sony"}),
        "actual_sku": "ELEC-SONY-WHCH720N-BLK",
        "amount": 9990.0,
        "category": "electronics",
        "merchant": "Amazon",
        "timestamp": "2026-08-15T11:00:00+00:00",
        "decision": "ALLOW",
        "session_id": "sess_drift_count_test",
    }]
    history_df = pd.DataFrame(history_rows)

    # Current candidate transaction #2 in same session
    tx2 = TransactionRequest(
        id="tx_drift_02",
        agent_id="agent_shopping_01",
        mandate_id=mandate.id,
        user_intent_id=intent.id,
        claimed_product={"sku": "ELEC-SONY-WHCH720N-BLK", "brand": "Sony", "model": "WH-CH720N", "specs": {"color": "black"}},
        actual_sku="ELEC-SONY-WHCH720N-BLK",
        amount=9990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
        scenario_type="legitimate_unusual",
        expected_decision="VERIFY",
        session_id="sess_drift_count_test",
    )

    receipt = evaluate_transaction(tx2, mandate, intent, catalog, None, history_df=history_df)

    assert receipt.decision == "VERIFY"
    assert "session goal drift detected (declared_item_count_exceeded)" in receipt.decision_reason
    assert receipt.goal_drift is not None
    assert receipt.goal_drift.has_drift is True
    assert receipt.goal_drift.reason == "declared_item_count_exceeded"
    assert receipt.trust_snapshot is not None
    assert receipt.trust_snapshot.purchase_session_id == "sess_drift_count_test"


def test_goal_drift_budget_exceeded_nudge_verify(catalog, mandates):
    """
    Scenario 2: Agent created a session declaring declared_total_budget = 15,000.
    Transaction #1 spent 9,990. Transaction #2 requests 9,990 (total projected 19,980 > 15,000).
    check_goal_drift flags session_budget_exceeded, which caps at VERIFY.
    """
    session = create_session(
        session_id="sess_drift_budget_test",
        intent_id="intent_drift_2",
        agent_id="agent_shopping_01",
        declared_item_count=5,
        declared_total_budget=15000.0, # Session budget 15k
    )

    mandate = mandates["mandate_shop_01"]
    intent = UserIntent(
        id="intent_drift_2",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-CH720N"},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    # History: 1 purchase of 9,990
    history_rows = [{
        "id": "tx_prior_01",
        "agent_id": "agent_shopping_01",
        "mandate_id": mandate.id,
        "user_intent_id": intent.id,
        "claimed_product": json.dumps({"brand": "Sony"}),
        "actual_sku": "ELEC-SONY-WHCH720N-BLK",
        "amount": 9990.0,
        "category": "electronics",
        "merchant": "Amazon",
        "timestamp": "2026-08-15T11:00:00+00:00",
        "decision": "ALLOW",
        "session_id": "sess_drift_budget_test",
    }]
    history_df = pd.DataFrame(history_rows)

    tx2 = TransactionRequest(
        id="tx_drift_budget_02",
        agent_id="agent_shopping_01",
        mandate_id=mandate.id,
        user_intent_id=intent.id,
        claimed_product={"sku": "ELEC-SONY-WHCH720N-BLK", "brand": "Sony", "model": "WH-CH720N", "specs": {"color": "black"}},
        actual_sku="ELEC-SONY-WHCH720N-BLK",
        amount=9990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc),
        scenario_type="legitimate_unusual",
        expected_decision="BLOCK",
        session_id="sess_drift_budget_test",
    )

    receipt = evaluate_transaction(tx2, mandate, intent, catalog, None, history_df=history_df)

    assert receipt.decision == "BLOCK"
    assert "session goal drift detected (session_budget_exceeded" in receipt.decision_reason
    assert receipt.goal_drift is not None
    assert receipt.goal_drift.has_drift is True
    assert receipt.goal_drift.reason == "session_budget_exceeded"


# -----------------------------------------------------------------------------
# TASK 13 & 14 TESTS: TrustSnapshot Generator and Persistence
# -----------------------------------------------------------------------------
def test_trust_snapshot_generation_and_schema(catalog, mandates):
    mandate = mandates["mandate_shop_01"]
    intent = UserIntent(
        id="intent_snap_test",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5"},
        soft_preferences={"color": "black"},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
        intent_version=2,
    )

    tx = TransactionRequest(
        id="tx_snap_001",
        agent_id="agent_shopping_01",
        mandate_id=mandate.id,
        user_intent_id=intent.id,
        claimed_product={"sku": "ELEC-SONY-WH1000XM5-BLK", "brand": "Sony", "model": "WH-1000XM5", "specs": {"color": "black"}},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=29990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 15, 11, 0, 0, tzinfo=timezone.utc),
        scenario_type="legitimate_unusual",
        expected_decision="ALLOW",
        session_id="sess_snap_test",
        intent_version=2,
    )

    receipt = evaluate_transaction(tx, mandate, intent, catalog, None)
    assert receipt.trust_snapshot is not None
    snap = receipt.trust_snapshot

    assert isinstance(snap, TrustSnapshot)
    assert snap.intent_id == "intent_snap_test"
    assert snap.intent_version == 2
    assert snap.mandate_id == mandate.id
    assert snap.mandate_version == 1
    assert snap.agent_id == "agent_shopping_01"
    assert snap.purchase_session_id == "sess_snap_test"
    assert snap.selected_sku == "ELEC-SONY-WH1000XM5-BLK"
    assert snap.amount == 29990.0
    assert snap.decision == receipt.decision
    assert len(snap.provenance_reference) >= 4


def test_trust_snapshot_db_persistence_and_api(client, tmp_path):
    test_db = tmp_path / "test_spendguard.db"
    init_db(test_db)

    tx_dict = {
        "id": "tx_db_snap_100",
        "agent_id": "agent_software_01",
        "mandate_id": "mandate_soft_01",
        "user_intent_id": "intent_soft_100",
        "amount": 24900.0,
        "category": "software",
        "merchant": "JetBrains",
        "timestamp": "2026-08-20T12:00:00+00:00",
        "claimed_product": {"brand": "JetBrains"},
        "actual_sku": "SOFT-JETBRAINS-ALLPROD-1YR",
        "session_id": "sess_software_100",
        "intent_version": 3,
    }

    mock_snapshot = {
        "trust_snapshot_id": "snap_tx_db_snap_100",
        "intent_id": "intent_soft_100",
        "intent_version": 3,
        "mandate_id": "mandate_soft_01",
        "mandate_version": 1,
        "agent_id": "agent_software_01",
        "purchase_session_id": "sess_software_100",
        "selected_sku": "SOFT-JETBRAINS-ALLPROD-1YR",
        "amount": 24900.0,
        "authorization_result": {"passed": True, "failed_checks": []},
        "intent_fidelity": {"hard_match": True},
        "evidence_result": {"conflicts": []},
        "behavioral_risk": {"score": 0.05, "top_reasons": []},
        "provenance_reference": [],
        "decision": "ALLOW",
        "decision_reason": "allowed: clean test",
        "decision_timestamp": "2026-08-20T12:00:00+00:00",
    }

    receipt_dict = {
        "transaction_id": "tx_db_snap_100",
        "authorization": {"passed": True, "failed_checks": []},
        "intent_fidelity": {"hard_match": True},
        "behavioral_risk": {"score": 0.05, "top_reasons": []},
        "evidence": {"conflicts": []},
        "goal_drift": {"has_drift": False},
        "provenance_trail": [],
        "decision": "ALLOW",
        "decision_reason": "allowed: clean test",
        "trust_snapshot": mock_snapshot,
    }

    save_transaction_evaluation(tx_dict, receipt_dict, actor="test", db_path=test_db)

    # Verify retrieval
    retrieved_receipt = get_transaction_receipt("tx_db_snap_100", db_path=test_db)
    assert retrieved_receipt is not None
    assert retrieved_receipt["session_id"] == "sess_software_100"
    assert retrieved_receipt["intent_version"] == 3
    assert retrieved_receipt["trust_snapshot"]["trust_snapshot_id"] == "snap_tx_db_snap_100"

    retrieved_snap = get_trust_snapshot("tx_db_snap_100", db_path=test_db)
    assert retrieved_snap is not None
    assert retrieved_snap["trust_snapshot_id"] == "snap_tx_db_snap_100"
    assert retrieved_snap["amount"] == 24900.0
