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
    
    assert receipt.decision == "BLOCK"
    assert "mandate_expired_past_ttl" in receipt.decision_reason or "authorization failed" in receipt.decision_reason
    assert receipt.authorization.is_stale is True
    assert receipt.intent_fidelity == "skipped"
    assert receipt.evidence == "skipped"
    assert receipt.behavioral_risk == "skipped"


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
        session_id=row.get("session_id") if "session_id" in row and pd.notna(row.get("session_id")) else None,
        intent_version=int(row.get("intent_version", 1)) if "intent_version" in row and pd.notna(row.get("intent_version")) else 1,
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
            session_id=row.get("session_id") if "session_id" in row and pd.notna(row.get("session_id")) else None,
            intent_version=int(row.get("intent_version", 1)) if "intent_version" in row and pd.notna(row.get("intent_version")) else 1,
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


def test_deceptive_split_payment_token_hard_blocks(repo_data):
    """
    Test that a deceptive installment token (e.g. 'Token 1 of 3') is escalated to a hard BLOCK
    at the trust gate rather than held at a soft VERIFY.
    """
    mandate = next(iter(repo_data["mandates"].values()))
    intent = UserIntent(
        id="intent_test_split_scam",
        agent_id="agent_01",
        hard_requirements={"category": "electronics", "brand": "Dell", "max_price": 100000.0},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    catalog = repo_data["catalog"]
    risk_model = repo_data["risk_model"]

    tx = TransactionRequest(
        id="test_split_scam_01",
        agent_id="agent_01",
        mandate_id=mandate.id,
        user_intent_id=intent.id,
        claimed_product={
            "sku": "ELEC-DELL-G15-4060",
            "brand": "Dell",
            "model": "G15 5530 (Installment Token 1 of 3)",
            "category": "electronics",
            "specs": {"ram_gb": 16, "installment_sequence": "1 of 3"},
        },
        actual_sku="ELEC-DELL-G15-4060",
        amount=9999.0,
        category="electronics",
        merchant="Croma", # whitelisted merchant
        timestamp=datetime.now(timezone.utc),
        scenario_type="price_split_bait",
        expected_decision="BLOCK",
    )

    receipt = evaluate_transaction(tx, mandate, intent, catalog, risk_model)
    assert receipt.decision == "BLOCK"
    assert "deceptive split-payment" in receipt.decision_reason
    assert receipt.behavioral_risk.score >= 0.75


def test_legitimate_authorized_emi_plan_resolves_verify(repo_data):
    """
    Test that a legitimate authorized EMI installment plan (e.g. 'No-Cost EMI')
    resolves to VERIFY for human pre-authorization rather than hard BLOCK.
    """
    mandate = next(iter(repo_data["mandates"].values()))
    intent = UserIntent(
        id="intent_test_emi",
        agent_id="agent_01",
        hard_requirements={"category": "electronics", "brand": "Dell", "max_price": 100000.0},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    catalog = repo_data["catalog"]
    risk_model = repo_data["risk_model"]

    tx = TransactionRequest(
        id="test_legit_emi_01",
        agent_id="agent_01",
        mandate_id=mandate.id,
        user_intent_id=intent.id,
        claimed_product={
            "sku": "ELEC-DELL-G15-4060",
            "brand": "Dell",
            "model": "G15 5530 (Authorized 3-Month No-Cost EMI)",
            "category": "electronics",
            "specs": {"tenure_months": 3, "monthly_emi": 32990.0, "ram_gb": 16, "storage_gb": 512, "display_inch": 15.6, "gpu": "RTX 4060", "cpu": "Intel Core i7-13650HX"},
        },
        actual_sku="ELEC-DELL-G15-4060",
        amount=32990.0,
        category="electronics",
        merchant="Dell Official Store",
        timestamp=datetime.now(timezone.utc),
        scenario_type="clean_baseline",
        expected_decision="VERIFY",
    )

    receipt = evaluate_transaction(tx, mandate, intent, catalog, risk_model)
    assert receipt.decision == "VERIFY"
    assert "authorized EMI installment plan" in receipt.decision_reason


def test_split_burst_with_high_risk_score_hard_blocks(repo_data):
    """
    Test that a sequence of split-charge bursts with high risk score hard blocks.
    """
    mandate = next(iter(repo_data["mandates"].values()))
    intent = UserIntent(
        id="intent_test_split_burst",
        agent_id="agent_01",
        hard_requirements={"category": "electronics", "brand": "Dell", "max_price": 100000.0},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    catalog = repo_data["catalog"]
    risk_model = repo_data["risk_model"]

    tx = TransactionRequest(
        id="test_split_burst_02",
        agent_id="agent_01",
        mandate_id=mandate.id,
        user_intent_id=intent.id,
        claimed_product={
            "sku": "ELEC-DELL-G15-4060",
            "brand": "Dell",
            "model": "G15 5530 (Split Charge 2 of 2)",
            "category": "electronics",
            "specs": {"split_order": "2 of 2"},
        },
        actual_sku="ELEC-DELL-G15-4060",
        amount=26900.0,
        category="electronics",
        merchant="Dell Official Store",
        timestamp=datetime.now(timezone.utc),
        scenario_type="price_split_bait",
        expected_decision="BLOCK",
    )

    receipt = evaluate_transaction(tx, mandate, intent, catalog, risk_model)
    assert receipt.decision == "BLOCK"
    assert "deceptive split-payment" in receipt.decision_reason


