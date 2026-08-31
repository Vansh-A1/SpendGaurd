import csv
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.db import init_db, get_audit_logs


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    # Use temporary or fresh DB for tests
    test_db = tmp_path / "test_spendguard.db"
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


def test_health_endpoint(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_evaluate_budget_violation(client, scenarios_data):
    bv_row = next(r for r in scenarios_data if r["scenario_type"] == "budget_violation")
    res = client.post("/transactions/evaluate", json=bv_row)
    assert res.status_code == 200
    receipt = res.json()
    assert receipt["decision"] == "BLOCK"
    assert "budget" in receipt["decision_reason"]
    assert receipt["intent_fidelity"] == "skipped"
    assert receipt["behavioral_risk"] == "skipped"
    assert receipt["evidence"] == "skipped"
    assert len(receipt["provenance_trail"]) > 0


def test_evaluate_and_human_verify_flow(client, scenarios_data):
    verify_row = next(r for r in scenarios_data if r["expected_decision"] == "VERIFY")
    tx_id = verify_row["id"]

    # 1. Evaluate policy hold -> expect VERIFY
    eval_res = client.post("/transactions/evaluate", json=verify_row)
    assert eval_res.status_code == 200
    eval_receipt = eval_res.json()
    assert eval_receipt["decision"] == "VERIFY"

    # 2. Human approval via POST /transactions/{id}/verify
    verify_res = client.post(f"/transactions/{tx_id}/verify", json={"approved": True})
    assert verify_res.status_code == 200
    updated_receipt = verify_res.json()
    assert updated_receipt["decision"] == "ALLOW"
    assert "human approved" in updated_receipt["decision_reason"]

    # 3. GET receipt confirms ALLOW
    receipt_res = client.get(f"/transactions/{tx_id}/receipt")
    assert receipt_res.status_code == 200
    assert receipt_res.json()["decision"] == "ALLOW"

    # 4. Confirm audit log has human actor
    audit_entries = get_audit_logs(tx_id)
    human_entry = next((e for e in audit_entries if e["actor"] == "human"), None)
    assert human_entry is not None
    assert human_entry["action"] == "approved"

    # 5. Attempting to verify again returns 409 Conflict
    conflict_res = client.post(f"/transactions/{tx_id}/verify", json={"approved": False})
    assert conflict_res.status_code == 409


def test_batch_evaluation_and_list_filtering(client, scenarios_data):
    # Batch post all transactions
    for row in scenarios_data:
        res = client.post("/transactions/evaluate", json=row)
        assert res.status_code == 200

    # GET /transactions returns all
    all_txs_res = client.get("/transactions")
    assert all_txs_res.status_code == 200
    all_txs = all_txs_res.json()
    assert len(all_txs) == len(scenarios_data)

    # Test filtering by decision
    blocks_res = client.get("/transactions?decision=BLOCK")
    assert blocks_res.status_code == 200
    blocks = blocks_res.json()
    assert len(blocks) > 0
    assert all(t["decision"] == "BLOCK" for t in blocks)

    # Test filtering by agent_id
    agent_txs_res = client.get("/transactions?agent_id=agent_shopping_01")
    assert agent_txs_res.status_code == 200
    agent_txs = agent_txs_res.json()
    assert len(agent_txs) > 0
    assert all(t["agent_id"] == "agent_shopping_01" for t in agent_txs)
