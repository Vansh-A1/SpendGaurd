import csv
import json
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.db import init_db
from payments.razorpay_client import create_test_order


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    test_db = tmp_path / "test_payments.db"
    init_db(test_db)
    from api import db
    old_db_path = db.DB_PATH
    db.DB_PATH = test_db
    yield
    db.DB_PATH = old_db_path


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def scenarios_data():
    repo_root = Path(__file__).resolve().parent.parent
    rows = []
    with open(repo_root / "data" / "scenarios.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["claimed_product"] = json.loads(r["claimed_product"])
            r["amount"] = float(r["amount"])
            rows.append(r)
    return rows


def test_allow_creates_razorpay_order(client, scenarios_data):
    legit_row = next(r for r in scenarios_data if r["scenario_type"] == "legitimate_unusual")

    # Mock razorpay order creation
    mock_order = {"id": "order_test_mock_12345", "amount": int(legit_row["amount"] * 100), "status": "created"}
    with patch("api.main.create_test_order", return_value=mock_order) as mock_create:
        res = client.post("/transactions/evaluate", json=legit_row)
        assert res.status_code == 200
        receipt = res.json()
        assert receipt["decision"] == "ALLOW"
        assert receipt["razorpay_order_id"] == "order_test_mock_12345"
        mock_create.assert_called_once()


def test_block_does_not_call_razorpay(client, scenarios_data):
    bv_row = next(r for r in scenarios_data if r["scenario_type"] == "budget_violation")

    with patch("api.main.create_test_order") as mock_create:
        res = client.post("/transactions/evaluate", json=bv_row)
        assert res.status_code == 200
        receipt = res.json()
        assert receipt["decision"] == "BLOCK"
        assert receipt.get("razorpay_order_id") is None
        mock_create.assert_not_called()


def test_verify_approval_creates_order_on_approval_only(client, scenarios_data):
    verify_row = next(r for r in scenarios_data if r["expected_decision"] == "VERIFY")
    tx_id = verify_row["id"]

    mock_order = {"id": "order_human_approved_67890", "amount": int(verify_row["amount"] * 100), "status": "created"}

    # 1. Evaluation produces VERIFY and does NOT call Razorpay
    with patch("api.main.create_test_order") as mock_create:
        eval_res = client.post("/transactions/evaluate", json=verify_row)
        assert eval_res.status_code == 200
        assert eval_res.json()["decision"] == "VERIFY"
        assert eval_res.json().get("razorpay_order_id") is None
        mock_create.assert_not_called()

    # 2. Human approval flips to ALLOW and calls Razorpay
    with patch("api.main.create_test_order", return_value=mock_order) as mock_create:
        verify_res = client.post(f"/transactions/{tx_id}/verify", json={"approved": True})
        assert verify_res.status_code == 200
        verified_receipt = verify_res.json()
        assert verified_receipt["decision"] == "ALLOW"
        assert verified_receipt["razorpay_order_id"] == "order_human_approved_67890"
        mock_create.assert_called_once()

    # 3. GET receipt confirms persisted razorpay_order_id
    receipt_res = client.get(f"/transactions/{tx_id}/receipt")
    assert receipt_res.status_code == 200
    assert receipt_res.json()["razorpay_order_id"] == "order_human_approved_67890"


def test_payment_failure_graceful_handling(client, scenarios_data):
    legit_row = next(r for r in scenarios_data if r["scenario_type"] == "legitimate_unusual")

    # Simulate Razorpay exception (e.g. invalid keys or network error)
    with patch("api.main.create_test_order", side_effect=Exception("Razorpay Authentication Error")):
        res = client.post("/transactions/evaluate", json=legit_row)
        assert res.status_code == 200
        receipt = res.json()
        assert receipt["decision"] == "ALLOW"
        assert receipt.get("razorpay_order_id") is None
        assert "Authentication Error" in receipt.get("payment_error", "")
