import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import pandas as pd

from api.main import app
from api.db import init_db, get_db_connection, get_transaction_receipt
from payments.razorpay_client import (
    create_test_order,
    create_payment_hold,
    capture_payment_hold,
    void_payment_hold,
    get_payment_hold,
    clear_payment_holds,
)
from api.escalations import (
    create_escalation,
    get_pending_escalations,
    process_escalation_timeouts,
    register_webhook,
    clear_webhooks,
    dispatch_escalation_webhook,
)
from session.manager import create_session, clear_sessions


@pytest.fixture(autouse=True)
def clean_state(tmp_path):
    clear_payment_holds()
    clear_sessions()
    clear_webhooks()
    test_db = tmp_path / "test_phase5.db"
    init_db(test_db)
    from api import db
    old_db_path = db.DB_PATH
    db.DB_PATH = test_db
    yield
    db.DB_PATH = old_db_path
    clear_payment_holds()
    clear_sessions()
    clear_webhooks()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# -----------------------------------------------------------------------------
# TASK 15 TESTS: Two-Phase Pre-Authorization, Hold, Capture & Void
# -----------------------------------------------------------------------------
def test_two_phase_payment_hold_and_capture():
    hold = create_payment_hold(amount=14999.0, currency="INR", transaction_id="tx_hold_001")
    assert hold["hold_id"].startswith("hold_")
    assert hold["status"] == "authorized"
    assert hold["amount"] == 14999.0
    assert hold["amount_in_paise"] == 1499900

    # Capture hold
    captured = capture_payment_hold(hold["hold_id"], amount=14999.0, transaction_id="tx_hold_001")
    assert captured["status"] == "captured"
    assert captured["razorpay_order_id"] is not None
    assert get_payment_hold(hold["hold_id"])["status"] == "captured"


def test_two_phase_payment_hold_and_void():
    hold = create_payment_hold(amount=25000.0, currency="INR", transaction_id="tx_hold_002")
    assert hold["status"] == "authorized"

    # Void hold
    voided = void_payment_hold(hold["hold_id"], reason="human_denied")
    assert voided["status"] == "voided"
    assert voided["reason"] == "human_denied"
    assert get_payment_hold(hold["hold_id"])["status"] == "voided"


# -----------------------------------------------------------------------------
# TASK 16 TESTS: Escalation Queue, SLA Timeouts & Webhook Dispatch
# -----------------------------------------------------------------------------
def test_escalation_queue_and_sla_remaining():
    now = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    esc = create_escalation(
        transaction_id="tx_esc_001",
        agent_id="agent_shopping_01",
        amount=19990.0,
        sla_minutes=15,
        payment_hold_id="hold_12345",
        current_time=now,
    )
    assert esc["status"] == "pending"

    # Check remaining time 5 minutes later
    check_time = now + timedelta(minutes=5)
    pending = get_pending_escalations(current_time=check_time)
    assert len(pending) == 1
    assert pending[0]["remaining_seconds"] == 600.0
    assert pending[0]["is_expired"] is False


def test_escalation_sla_timeout_auto_denial_and_hold_void():
    start_time = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
    hold = create_payment_hold(amount=19990.0, currency="INR", transaction_id="tx_esc_timeout_001")

    create_escalation(
        transaction_id="tx_esc_timeout_001",
        agent_id="agent_shopping_01",
        amount=19990.0,
        sla_minutes=15,
        payment_hold_id=hold["hold_id"],
        current_time=start_time,
    )

    # Fast forward 16 minutes (exceeding 15m SLA)
    timeout_time = start_time + timedelta(minutes=16)
    timed_out_items = process_escalation_timeouts(current_time=timeout_time)

    assert len(timed_out_items) == 1
    assert timed_out_items[0]["transaction_id"] == "tx_esc_timeout_001"
    assert timed_out_items[0]["action_taken"] == "auto_denied_and_hold_voided"

    # Confirm hold is voided
    assert get_payment_hold(hold["hold_id"])["status"] == "voided"
    assert get_payment_hold(hold["hold_id"])["void_reason"] == "sla_timeout"


def test_escalation_webhook_dispatch():
    register_webhook("https://httpbin.org/post")
    tx_data = {"id": "tx_hook_1", "agent_id": "agent_shopping_01", "amount": 9990.0}
    receipt_data = {"decision": "VERIFY", "decision_reason": "test review", "payment_hold_id": "hold_test"}

    # Test graceful dispatch
    with patch("urllib.request.urlopen") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_post.return_value.__enter__.return_value = mock_resp
        success = dispatch_escalation_webhook(tx_data, receipt_data)
        assert success is True
        mock_post.assert_called_once()


# -----------------------------------------------------------------------------
# TASK 18: 5 End-to-End Payment Flow Scenarios
# -----------------------------------------------------------------------------
def test_e2e_scenario_1_allow_immediate_order(client):
    """Scenario 1: ALLOW transaction -> Immediate Razorpay Order."""
    tx_req = {
        "id": "tx_e2e_001",
        "agent_id": "agent_shopping_01",
        "mandate_id": "mandate_shop_01",
        "user_intent_id": "intent_0101",
        "claimed_product": {"sku": "ELEC-SONY-WH1000XM5-BLK", "brand": "Sony", "model": "WH-1000XM5", "specs": {"anc": True, "battery_hours": 30, "color": "black", "form_factor": "over-ear", "driver_mm": 30}},
        "actual_sku": "ELEC-SONY-WH1000XM5-BLK",
        "amount": 29990.0,
        "category": "electronics",
        "merchant": "Sony Center",
        "timestamp": "2026-08-18T16:00:00+00:00",
        "scenario_type": "legitimate_unusual",
        "expected_decision": "ALLOW",
    }

    mock_order = {"id": "order_e2e_allow_111", "amount": 2999000, "status": "created"}
    with patch("api.main.create_test_order", return_value=mock_order):
        res = client.post("/transactions/evaluate", json=tx_req)
        assert res.status_code == 200
        receipt = res.json()
        assert receipt["decision"] == "ALLOW"
        assert receipt["razorpay_order_id"] == "order_e2e_allow_111"
        assert receipt.get("payment_hold_id") is None


def test_e2e_scenario_2_verify_hold_then_approved_and_captured(client):
    """Scenario 2: VERIFY transaction -> Hold created -> Human Approved -> Captured."""
    tx_req = {
        "id": "tx_e2e_002",
        "agent_id": "agent_shopping_01",
        "mandate_id": "mandate_shop_01",
        "user_intent_id": "intent_0035", # Substitution intent
        "claimed_product": {"sku": "ELEC-SONY-WH1000XM5-BLK", "brand": "Sony", "model": "WH-1000XM5", "specs": {"anc": True, "battery_hours": 30, "color": "black", "form_factor": "over-ear", "driver_mm": 30}},
        "actual_sku": "ELEC-SONY-WH1000XM5-BLK",
        "amount": 29990.0,
        "category": "electronics",
        "merchant": "Sony Center",
        "timestamp": "2026-08-15T13:24:00+00:00",
        "scenario_type": "substitution",
        "expected_decision": "VERIFY",
    }

    # Step 1: Evaluation creates VERIFY and authorization hold
    eval_res = client.post("/transactions/evaluate", json=tx_req)
    assert eval_res.status_code == 200
    receipt = eval_res.json()
    assert receipt["decision"] == "VERIFY"
    assert receipt.get("payment_hold_id") is not None
    hold_id = receipt["payment_hold_id"]
    assert get_payment_hold(hold_id)["status"] == "authorized"

    # Step 2: Human approves transaction -> hold captured
    mock_order = {"id": "order_captured_e2e_222", "amount": 2999000, "status": "created"}
    with patch("api.main.create_test_order", return_value=mock_order):
        ver_res = client.post(f"/transactions/{tx_req['id']}/verify", json={"approved": True})
        assert ver_res.status_code == 200
        ver_receipt = ver_res.json()
        assert ver_receipt["decision"] == "ALLOW"
        assert ver_receipt["razorpay_order_id"] == "order_captured_e2e_222"
        assert get_payment_hold(hold_id)["status"] == "captured"


def test_e2e_scenario_3_verify_hold_then_denied_and_voided(client):
    """Scenario 3: VERIFY transaction -> Hold created -> Human Denied -> Voided."""
    tx_req = {
        "id": "tx_e2e_003",
        "agent_id": "agent_shopping_01",
        "mandate_id": "mandate_shop_01",
        "user_intent_id": "intent_0035",
        "claimed_product": {"sku": "ELEC-SONY-WH1000XM5-BLK", "brand": "Sony", "model": "WH-1000XM5", "specs": {"anc": True, "battery_hours": 30, "color": "black", "form_factor": "over-ear", "driver_mm": 30}},
        "actual_sku": "ELEC-SONY-WH1000XM5-BLK",
        "amount": 29990.0,
        "category": "electronics",
        "merchant": "Sony Center",
        "timestamp": "2026-08-15T13:24:00+00:00",
        "scenario_type": "substitution",
        "expected_decision": "VERIFY",
    }

    eval_res = client.post("/transactions/evaluate", json=tx_req)
    assert eval_res.status_code == 200
    receipt = eval_res.json()
    assert receipt["decision"] == "VERIFY"
    hold_id = receipt["payment_hold_id"]
    assert get_payment_hold(hold_id)["status"] == "authorized"

    # Human denies transaction -> hold voided
    ver_res = client.post(f"/transactions/{tx_req['id']}/verify", json={"approved": False})
    assert ver_res.status_code == 200
    ver_receipt = ver_res.json()
    assert ver_receipt["decision"] == "BLOCK"
    assert ver_receipt.get("razorpay_order_id") is None
    assert get_payment_hold(hold_id)["status"] == "voided"
    assert get_payment_hold(hold_id)["void_reason"] == "human_denied"


def test_e2e_scenario_4_verify_hold_sla_timeout_auto_denied(client):
    """Scenario 4: VERIFY transaction -> SLA Timeout without action -> Auto-denied + Voided."""
    tx_req = {
        "id": "tx_e2e_004",
        "agent_id": "agent_shopping_01",
        "mandate_id": "mandate_shop_01",
        "user_intent_id": "intent_0035",
        "claimed_product": {"sku": "ELEC-SONY-WH1000XM5-BLK", "brand": "Sony", "model": "WH-1000XM5", "specs": {"anc": True, "battery_hours": 30, "color": "black", "form_factor": "over-ear", "driver_mm": 30}},
        "actual_sku": "ELEC-SONY-WH1000XM5-BLK",
        "amount": 29990.0,
        "category": "electronics",
        "merchant": "Sony Center",
        "timestamp": "2026-08-15T13:24:00+00:00",
        "scenario_type": "substitution",
        "expected_decision": "VERIFY",
    }

    eval_res = client.post("/transactions/evaluate", json=tx_req)
    assert eval_res.status_code == 200
    hold_id = eval_res.json()["payment_hold_id"]
    assert get_payment_hold(hold_id)["status"] == "authorized"

    # Simulate timeout execution
    now_plus_16m = datetime.now(timezone.utc) + timedelta(minutes=16)
    timeout_res = process_escalation_timeouts(current_time=now_plus_16m)
    assert any(t["transaction_id"] == "tx_e2e_004" for t in timeout_res)

    # Check updated receipt
    receipt_res = client.get("/transactions/tx_e2e_004/receipt")
    assert receipt_res.status_code == 200
    r = receipt_res.json()
    assert r["decision"] == "BLOCK"
    assert "SLA timeout expired" in r["decision_reason"]
    assert get_payment_hold(hold_id)["status"] == "voided"


def test_e2e_scenario_5_block_no_payment_or_hold(client):
    """Scenario 5: BLOCK transaction -> Zero payment order or hold created."""
    tx_req = {
        "id": "tx_e2e_005",
        "agent_id": "agent_shopping_01",
        "mandate_id": "mandate_shop_01",
        "user_intent_id": "intent_0001",
        "claimed_product": {"brand": "Apple"},
        "actual_sku": "ELEC-APPLE-MACBOOKAIR-M3",
        "amount": 114900.0, # Exceeds 40,000 cap
        "category": "electronics",
        "merchant": "Amazon",
        "timestamp": "2026-08-15T12:00:00+00:00",
        "scenario_type": "budget_violation",
        "expected_decision": "BLOCK",
    }

    res = client.post("/transactions/evaluate", json=tx_req)
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["decision"] == "BLOCK"
    assert receipt.get("razorpay_order_id") is None
    assert receipt.get("payment_hold_id") is None
