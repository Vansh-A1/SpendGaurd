import csv
import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pytest

from data.schema import TransactionRequest, Product
from policy.schema import Mandate
from intent.schema import UserIntent
from data.catalog import get_catalog
from decision.engine import evaluate_transaction, DecisionReceipt


@pytest.fixture
def repo_data():
    repo_root = Path(__file__).resolve().parent.parent
    catalog = get_catalog()
    
    with open(repo_root / "data" / "mandates.json", "r", encoding="utf-8") as f:
        mandates = {m["id"]: Mandate(**m) for m in json.load(f)}

    with open(repo_root / "data" / "intents.json", "r", encoding="utf-8") as f:
        intents = {k: UserIntent(**v) for k, v in json.load(f).items()}

    with open(repo_root / "model" / "risk_model.pkl", "rb") as f:
        risk_model = pickle.load(f)

    scenarios_df = pd.read_csv(repo_root / "data" / "scenarios.csv")

    return {
        "catalog": catalog,
        "mandates": mandates,
        "intents": intents,
        "risk_model": risk_model,
        "scenarios_df": scenarios_df,
    }


def test_budget_violation_terminates_at_step_1(repo_data):
    scenarios_df = repo_data["scenarios_df"]
    row = scenarios_df[scenarios_df["scenario_type"] == "budget_violation"].iloc[0]
    
    tx = TransactionRequest(
        id=row["id"],
        agent_id=row["agent_id"],
        mandate_id=row["mandate_id"],
        user_intent_id=row["user_intent_id"],
        claimed_product=json.loads(row["claimed_product"]),
        actual_sku=row["actual_sku"],
        amount=float(row["amount"]),
        category=row["category"],
        merchant=row["merchant"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        scenario_type=row["scenario_type"],
        expected_decision=row["expected_decision"],
    )
    mandate = repo_data["mandates"][tx.mandate_id]
    intent = repo_data["intents"][tx.user_intent_id]

    receipt = evaluate_transaction(tx, mandate, intent, repo_data["catalog"], repo_data["risk_model"])
    
    assert receipt.decision == "BLOCK"
    assert "budget" in receipt.decision_reason
    assert receipt.authorization.passed is False
    assert receipt.intent_fidelity == "skipped"
    assert receipt.behavioral_risk == "skipped"
    assert receipt.evidence == "skipped"


def test_wrong_product_terminates_at_step_2(repo_data):
    scenarios_df = repo_data["scenarios_df"]
    row = scenarios_df[scenarios_df["scenario_type"] == "wrong_product"].iloc[0]
    
    tx = TransactionRequest(
        id=row["id"],
        agent_id=row["agent_id"],
        mandate_id=row["mandate_id"],
        user_intent_id=row["user_intent_id"],
        claimed_product=json.loads(row["claimed_product"]),
        actual_sku=row["actual_sku"],
        amount=float(row["amount"]),
        category=row["category"],
        merchant=row["merchant"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        scenario_type=row["scenario_type"],
        expected_decision=row["expected_decision"],
    )
    mandate = repo_data["mandates"][tx.mandate_id]
    intent = repo_data["intents"][tx.user_intent_id]

    receipt = evaluate_transaction(tx, mandate, intent, repo_data["catalog"], repo_data["risk_model"])
    
    assert receipt.decision == "BLOCK"
    assert "intent fidelity" in receipt.decision_reason
    assert receipt.authorization.passed is True
    assert receipt.intent_fidelity.hard_match is False
    assert receipt.behavioral_risk == "skipped"
    assert receipt.evidence == "skipped"


def test_evidence_conflict_hard_terminates_at_step_3(repo_data):
    scenarios_df = repo_data["scenarios_df"]
    row = scenarios_df[scenarios_df["scenario_type"] == "evidence_conflict"].iloc[0]
    
    tx = TransactionRequest(
        id=row["id"],
        agent_id=row["agent_id"],
        mandate_id=row["mandate_id"],
        user_intent_id=row["user_intent_id"],
        claimed_product=json.loads(row["claimed_product"]),
        actual_sku=row["actual_sku"],
        amount=float(row["amount"]),
        category=row["category"],
        merchant=row["merchant"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        scenario_type=row["scenario_type"],
        expected_decision=row["expected_decision"],
    )
    mandate = repo_data["mandates"][tx.mandate_id]
    intent = repo_data["intents"][tx.user_intent_id]

    receipt = evaluate_transaction(tx, mandate, intent, repo_data["catalog"], repo_data["risk_model"])
    
    assert receipt.decision == "BLOCK"
    assert "evidence conflict" in receipt.decision_reason
    assert receipt.authorization.passed is True
    assert receipt.intent_fidelity.hard_match is True
    assert len(receipt.evidence.conflicts) > 0
    assert receipt.behavioral_risk == "skipped"


def test_stale_mandate_nudged_to_verify(repo_data):
    scenarios_df = repo_data["scenarios_df"]
    row = scenarios_df[scenarios_df["scenario_type"] == "stale_mandate"].iloc[0]
    
    tx = TransactionRequest(
        id=row["id"],
        agent_id=row["agent_id"],
        mandate_id=row["mandate_id"],
        user_intent_id=row["user_intent_id"],
        claimed_product=json.loads(row["claimed_product"]),
        actual_sku=row["actual_sku"],
        amount=float(row["amount"]),
        category=row["category"],
        merchant=row["merchant"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        scenario_type=row["scenario_type"],
        expected_decision=row["expected_decision"],
    )
    mandate = repo_data["mandates"][tx.mandate_id]
    intent = repo_data["intents"][tx.user_intent_id]

    history_df = scenarios_df.iloc[:row.name]
    receipt = evaluate_transaction(tx, mandate, intent, repo_data["catalog"], repo_data["risk_model"], history_df=history_df)
    
    assert receipt.decision == "VERIFY"
    assert "stale" in receipt.decision_reason
    assert receipt.authorization.passed is True
    assert receipt.authorization.is_stale is True
    assert receipt.intent_fidelity.hard_match is True
    assert receipt.evidence.conflicts == []
    assert receipt.behavioral_risk.score < 0.70


def test_split_payment_blocks_from_risk(repo_data):
    scenarios_df = repo_data["scenarios_df"]
    # Pick the 10th row of split_payment pattern to have high trailing velocity
    split_rows = scenarios_df[scenarios_df["scenario_type"] == "split_payment"]
    row = split_rows.iloc[9]
    
    tx = TransactionRequest(
        id=row["id"],
        agent_id=row["agent_id"],
        mandate_id=row["mandate_id"],
        user_intent_id=row["user_intent_id"],
        claimed_product=json.loads(row["claimed_product"]),
        actual_sku=row["actual_sku"],
        amount=float(row["amount"]),
        category=row["category"],
        merchant=row["merchant"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        scenario_type=row["scenario_type"],
        expected_decision=row["expected_decision"],
    )
    mandate = repo_data["mandates"][tx.mandate_id]
    intent = repo_data["intents"][tx.user_intent_id]

    # Pass prior history from scenarios_df up to this row
    history_df = scenarios_df.iloc[:row.name]
    receipt = evaluate_transaction(tx, mandate, intent, repo_data["catalog"], repo_data["risk_model"], history_df=history_df)
    
    assert receipt.decision == "BLOCK"
    assert "risk score" in receipt.decision_reason
    assert receipt.behavioral_risk.score > 0.70


def test_legitimate_unusual_resolves_allow(repo_data):
    scenarios_df = repo_data["scenarios_df"]
    row = scenarios_df[scenarios_df["scenario_type"] == "legitimate_unusual"].iloc[0]
    
    tx = TransactionRequest(
        id=row["id"],
        agent_id=row["agent_id"],
        mandate_id=row["mandate_id"],
        user_intent_id=row["user_intent_id"],
        claimed_product=json.loads(row["claimed_product"]),
        actual_sku=row["actual_sku"],
        amount=float(row["amount"]),
        category=row["category"],
        merchant=row["merchant"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        scenario_type=row["scenario_type"],
        expected_decision=row["expected_decision"],
    )
    mandate = repo_data["mandates"][tx.mandate_id]
    intent = repo_data["intents"][tx.user_intent_id]

    receipt = evaluate_transaction(tx, mandate, intent, repo_data["catalog"], repo_data["risk_model"])
    
    assert receipt.decision == "ALLOW"
    assert "allowed" in receipt.decision_reason
    assert receipt.authorization.passed is True
    assert receipt.intent_fidelity.hard_match is True
    assert receipt.evidence.conflicts == []
    assert receipt.behavioral_risk.score < 0.30


def test_full_scenarios_batch_match_rate(repo_data):
    scenarios_df = repo_data["scenarios_df"]
    catalog = repo_data["catalog"]
    mandates = repo_data["mandates"]
    intents = repo_data["intents"]
    risk_model = repo_data["risk_model"]

    total = len(scenarios_df)
    matches = 0
    mismatches = []

    for idx, row in scenarios_df.iterrows():
        tx = TransactionRequest(
            id=row["id"],
            agent_id=row["agent_id"],
            mandate_id=row["mandate_id"],
            user_intent_id=row["user_intent_id"],
            claimed_product=json.loads(row["claimed_product"]),
            actual_sku=row["actual_sku"],
            amount=float(row["amount"]),
            category=row["category"],
            merchant=row["merchant"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            scenario_type=row["scenario_type"],
            expected_decision=row["expected_decision"],
        )
        mandate = mandates[tx.mandate_id]
        intent = intents[tx.user_intent_id]
        history_df = scenarios_df.iloc[:idx]

        receipt = evaluate_transaction(tx, mandate, intent, catalog, risk_model, history_df=history_df)

        if receipt.decision == tx.expected_decision:
            matches += 1
        else:
            mismatches.append({
                "id": tx.id,
                "scenario_type": tx.scenario_type,
                "expected": tx.expected_decision,
                "actual": receipt.decision,
                "reason": receipt.decision_reason,
            })

    match_rate = matches / total
    print(f"\nBatch Evaluation Result: {matches}/{total} matches ({match_rate * 100:.1f}%)")

    if mismatches:
        print("\nMismatches Detail:")
        for m in mismatches:
            print(f"  - [{m['id']}] {m['scenario_type']}: Expected={m['expected']}, Actual={m['actual']} | Reason: {m['reason']}")

    assert match_rate >= 0.90, f"Match rate {match_rate * 100:.1f}% is below 90%"
