import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from data.schema import TransactionRequest
from policy.schema import Mandate
from policy.authorization import check_authorization, AuthorizationResult


@pytest.fixture
def sample_mandate():
    return Mandate(
        id="mandate_test_01",
        agent_id="agent_test_01",
        per_transaction_cap=40000.0,
        categories=["electronics"],
        merchants=["Amazon", "Croma", "Sony Center"],
        time_window_start="08:00",
        time_window_end="22:00",
        issued_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=30 * 86400,  # 30 days
    )


@pytest.fixture
def base_valid_tx():
    return TransactionRequest(
        id="tx_valid_01",
        agent_id="agent_test_01",
        mandate_id="mandate_test_01",
        user_intent_id="intent_test_01",
        claimed_product={"sku": "ELEC-SONY-WH1000XM5-BLK"},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=29990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 15, 14, 0, 0, tzinfo=timezone.utc),
        scenario_type="legitimate_unusual",
        expected_decision="ALLOW",
    )


def test_fully_valid_transaction(sample_mandate, base_valid_tx):
    result = check_authorization(base_valid_tx, sample_mandate)
    assert result.passed is True
    assert result.failed_checks == []
    assert result.is_stale is False


def test_budget_over_only(sample_mandate, base_valid_tx):
    tx = base_valid_tx.model_copy(update={"amount": 45000.0})
    result = check_authorization(tx, sample_mandate)
    assert result.passed is False
    assert result.failed_checks == ["budget_exceeded"]
    assert result.is_stale is False


def test_wrong_category_only(sample_mandate, base_valid_tx):
    tx = base_valid_tx.model_copy(update={"category": "travel"})
    result = check_authorization(tx, sample_mandate)
    assert result.passed is False
    assert result.failed_checks == ["category_not_allowed"]
    assert result.is_stale is False


def test_wrong_merchant_only(sample_mandate, base_valid_tx):
    tx = base_valid_tx.model_copy(update={"merchant": "UnapprovedStore"})
    result = check_authorization(tx, sample_mandate)
    assert result.passed is False
    assert result.failed_checks == ["merchant_not_allowed"]
    assert result.is_stale is False


def test_outside_time_window_only(sample_mandate, base_valid_tx):
    # Timestamp at 03:00 AM (window is 08:00 to 22:00)
    tx = base_valid_tx.model_copy(
        update={"timestamp": datetime(2026, 8, 15, 3, 0, 0, tzinfo=timezone.utc)}
    )
    result = check_authorization(tx, sample_mandate)
    assert result.passed is False
    assert result.failed_checks == ["outside_time_window"]
    assert result.is_stale is False


def test_stale_mandate_but_otherwise_valid(sample_mandate, base_valid_tx):
    # Timestamp past 30 days expiry (e.g. 45 days after mandate issued_at)
    stale_time = sample_mandate.issued_at + timedelta(days=45, hours=4)
    tx = base_valid_tx.model_copy(update={"timestamp": stale_time})
    result = check_authorization(tx, sample_mandate)
    assert result.passed is True
    assert result.failed_checks == []
    assert result.is_stale is True


def test_multiple_failures_at_once(sample_mandate, base_valid_tx):
    # Fails budget, category, merchant, and time window simultaneously
    tx = base_valid_tx.model_copy(
        update={
            "amount": 99999.0,
            "category": "software",
            "merchant": "UnauthorizedVendor",
            "timestamp": datetime(2026, 8, 15, 1, 0, 0, tzinfo=timezone.utc),
        }
    )
    result = check_authorization(tx, sample_mandate)
    assert result.passed is False
    assert set(result.failed_checks) == {
        "budget_exceeded",
        "category_not_allowed",
        "merchant_not_allowed",
        "outside_time_window",
    }
    assert result.is_stale is False


def test_sampled_scenarios_from_csv():
    data_dir = Path(__file__).resolve().parent.parent / "data"
    with open(data_dir / "mandates.json", "r", encoding="utf-8") as f:
        mandates_dict = {m["id"]: Mandate(**m) for m in json.load(f)}

    rows = []
    with open(data_dir / "scenarios.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["claimed_product"] = json.loads(r["claimed_product"])
            r["amount"] = float(r["amount"])
            rows.append(TransactionRequest(**r))

    # Sample rows across different scenario types
    for tx in rows:
        mandate = mandates_dict[tx.mandate_id]
        res = check_authorization(tx, mandate)

        if tx.scenario_type == "budget_violation":
            assert res.passed is False
            assert "budget_exceeded" in res.failed_checks
        elif tx.scenario_type == "stale_mandate":
            assert res.passed is True
            assert res.is_stale is True
        elif tx.scenario_type in ["substitution", "wrong_product", "evidence_conflict", "legitimate_unusual", "split_payment"]:
            # In these scenarios, authorization checks 1-4 pass individually
            assert res.passed is True
            assert res.failed_checks == []
