import csv
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from data.schema import Product, TransactionRequest
from intent.schema import UserIntent
from intent.fidelity import check_intent_fidelity, IntentFidelityResult
from data.catalog import get_catalog


@pytest.fixture
def sample_product():
    return Product(
        sku="ELEC-SONY-WH1000XM5-BLK",
        brand="Sony",
        model="WH-1000XM5",
        category="electronics",
        price=29990.0,
        specs={"anc": True, "battery_hours": 30, "color": "black", "driver_mm": 30},
    )


def test_exact_hard_match_no_soft_preferences(sample_product):
    intent = UserIntent(
        id="intent_test_01",
        agent_id="agent_test_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5", "category": "electronics"},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    result = check_intent_fidelity(intent, sample_product)
    assert result.hard_match is True
    assert result.soft_score == 1.0
    assert result.mismatched_fields == []


def test_hard_mismatch_on_brand(sample_product):
    intent = UserIntent(
        id="intent_test_02",
        agent_id="agent_test_01",
        hard_requirements={"brand": "Bose", "category": "electronics"},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    result = check_intent_fidelity(intent, sample_product)
    assert result.hard_match is False
    assert "brand" in result.mismatched_fields


def test_hard_match_with_missed_soft_preference(sample_product):
    intent = UserIntent(
        id="intent_test_03",
        agent_id="agent_test_01",
        hard_requirements={"brand": "Sony", "category": "electronics"},
        soft_preferences={"color": "silver", "anc": True},  # color is 'black', anc is True (1 match out of 2)
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    result = check_intent_fidelity(intent, sample_product)
    assert result.hard_match is True
    assert result.soft_score == 0.5  # 1 / 2 matched
    assert result.mismatched_fields == []


def test_max_price_ceiling_requirement(sample_product):
    # actual price is 29990, ceiling is 35000 -> should pass
    intent_pass = UserIntent(
        id="intent_test_04",
        agent_id="agent_test_01",
        hard_requirements={"brand": "Sony", "max_price": 35000.0},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    result_pass = check_intent_fidelity(intent_pass, sample_product)
    assert result_pass.hard_match is True
    assert result_pass.mismatched_fields == []

    # actual price is 29990, ceiling is 25000 -> should fail
    intent_fail = UserIntent(
        id="intent_test_05",
        agent_id="agent_test_01",
        hard_requirements={"brand": "Sony", "max_price": 25000.0},
        soft_preferences={},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    result_fail = check_intent_fidelity(intent_fail, sample_product)
    assert result_fail.hard_match is False
    assert "max_price" in result_fail.mismatched_fields


def test_free_text_unmapped_soft_preference(sample_product):
    # Free-text notes that don't map to a spec key should be ignored
    intent = UserIntent(
        id="intent_test_06",
        agent_id="agent_test_01",
        hard_requirements={"brand": "Sony"},
        soft_preferences={"notes": "please deliver fast with good packaging"},
        substitution_allowed=False,
        created_at=datetime.now(timezone.utc),
    )
    result = check_intent_fidelity(intent, sample_product)
    assert result.hard_match is True
    assert result.soft_score == 1.0  # no scoreable attributes, defaults to 1.0


def test_scenarios_dataset_fidelity():
    data_dir = Path(__file__).resolve().parent.parent / "data"
    catalog_by_sku = {p.sku: p for p in get_catalog()}

    with open(data_dir / "intents.json", "r", encoding="utf-8") as f:
        intents_by_id = {k: UserIntent(**v) for k, v in json.load(f).items()}

    rows = []
    with open(data_dir / "scenarios.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["claimed_product"] = json.loads(r["claimed_product"])
            r["amount"] = float(r["amount"])
            rows.append(TransactionRequest(**r))

    for tx in rows:
        intent = intents_by_id.get(tx.user_intent_id)
        assert intent is not None, f"Missing intent for {tx.id}"
        product = catalog_by_sku[tx.actual_sku]
        res = check_intent_fidelity(intent, product)

        if tx.scenario_type == "legitimate_unusual":
            # Legitimate transactions must satisfy all hard requirements
            assert res.hard_match is True, f"Legitimate unusual failed fidelity: {res.mismatched_fields}"
            assert res.mismatched_fields == []

        elif tx.scenario_type == "wrong_product":
            # Wrong product transactions must fail hard match
            assert res.hard_match is False, f"Wrong product unexpectedly passed fidelity for tx {tx.id}"
            assert len(res.mismatched_fields) > 0

        elif tx.scenario_type == "substitution":
            # Substitution cases have substitution_allowed=True, with a near-match on model/spec
            assert intent.substitution_allowed is True
            # The model is substituted so exact hard model requirement differs
            assert res.hard_match is False
            assert "model" in res.mismatched_fields or "category" in res.mismatched_fields or len(res.mismatched_fields) > 0
