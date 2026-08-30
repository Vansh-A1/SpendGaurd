import csv
import json
from pathlib import Path
import pytest

from data.schema import Product, TransactionRequest
from intent.schema import UserIntent
from data.catalog import get_catalog, get_product_by_sku
from evidence.check import check_evidence, EvidenceResult
from evidence.provenance import (
    log_provenance_event,
    build_provenance_trail,
    get_provenance_for_transaction,
    clear_provenance_log,
)


@pytest.fixture
def catalog():
    return get_catalog()


def test_clean_evidence_match(catalog):
    claimed = {
        "sku": "ELEC-SONY-WH1000XM5-BLK",
        "brand": "Sony",
        "model": "WH-1000XM5",
        "category": "electronics",
        "price": 29990.0,
        "specs": {"anc": True, "battery_hours": 30, "driver_mm": 30, "color": "black"},
    }
    result = check_evidence(claimed, "ELEC-SONY-WH1000XM5-BLK", catalog)
    assert isinstance(result, EvidenceResult)
    assert result.sources_checked == ["catalog_spec"]
    assert result.conflicts == []


def test_deliberate_spec_mismatch(catalog):
    # Dell G15 with RTX 3050 in catalog, but claimed RTX 4060
    claimed = {
        "sku": "ELEC-DELL-G15-3050",
        "brand": "Dell",
        "model": "G15 5530 (RTX 4060)",
        "specs": {"gpu": "RTX 4060", "cpu": "Intel Core i7-13650HX", "ram_gb": 16},
    }
    result = check_evidence(claimed, "ELEC-DELL-G15-3050", catalog)
    assert len(result.conflicts) > 0
    gpu_conflicts = [c for c in result.conflicts if c["field"] == "gpu"]
    assert len(gpu_conflicts) == 1
    assert gpu_conflicts[0]["claimed"] == "RTX 4060"
    assert gpu_conflicts[0]["actual"] == "RTX 3050"


def test_unknown_sku_conflict(catalog):
    claimed = {"brand": "FakeBrand", "model": "GhostModel"}
    result = check_evidence(claimed, "ELEC-NONEXISTENT-SKU-999", catalog)
    assert len(result.conflicts) == 1
    assert result.conflicts[0]["field"] == "sku"
    assert result.conflicts[0]["actual"] == "not_found"


def test_scenarios_dataset_evidence_checks(catalog):
    data_dir = Path(__file__).resolve().parent.parent / "data"
    rows = []
    with open(data_dir / "scenarios.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["claimed_product"] = json.loads(r["claimed_product"])
            r["amount"] = float(r["amount"])
            rows.append(TransactionRequest(**r))

    for tx in rows:
        result = check_evidence(tx.claimed_product, tx.actual_sku, catalog)

        if tx.scenario_type == "evidence_conflict":
            assert len(result.conflicts) > 0, f"Expected evidence conflicts for tx {tx.id}, but found none"
        elif tx.scenario_type == "legitimate_unusual":
            assert len(result.conflicts) == 0, f"Expected clean evidence for legit tx {tx.id}, got {result.conflicts}"


def test_provenance_trail_synthesis(catalog):
    clear_provenance_log()

    sub_intent = UserIntent(
        id="intent_sub_test",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-CH720N", "category": "electronics"},
        soft_preferences={"color": "black", "anc": True},
        substitution_allowed=True,
        created_at=get_product_by_sku("ELEC-SONY-WHCH520-BLK").price, # arbitrary
    )

    trail = build_provenance_trail(
        transaction_id="tx_sub_sample",
        intent=sub_intent,
        catalog=catalog,
        selected_sku="ELEC-SONY-WHCH520-BLK",
    )

    assert len(trail) >= 4
    event_types = [e["event_type"] for e in trail]
    assert event_types == ["search", "candidates_found", "candidates_eliminated", "selected"]

    # Verify search query
    assert trail[0]["payload"]["query"]["brand"] == "Sony"

    # Verify candidate elimination reasons
    elim_payload = trail[2]["payload"]
    assert elim_payload["eliminated_count"] > 0
    # Spot-check Bose QC45 elimination reason
    bose_elim = next((e for e in elim_payload["eliminations"] if e["brand"] == "Bose"), None)
    if bose_elim:
        assert any("brand 'Bose' != requested 'Sony'" in r for r in bose_elim["reasons"])

    # Verify final selection
    selected_payload = trail[3]["payload"]
    assert selected_payload["sku"] == "ELEC-SONY-WHCH520-BLK"
    assert "substitute" in selected_payload["reason"]


def test_unverifiable_evidence_handling(catalog):
    # Claimed spec attribute 'connector' does not exist in AirPods Pro 2 catalog specs (which uses 'charging')
    claimed = {
        "sku": "ELEC-APPLE-AIRPODSPRO2",
        "brand": "Apple",
        "model": "AirPods Pro (2nd Gen)",
        "specs": {"connector": "Lightning", "anc": True},
    }
    result = check_evidence(claimed, "ELEC-APPLE-AIRPODSPRO2", catalog)
    assert isinstance(result, EvidenceResult)
    assert result.verification_status == "unverifiable"
    assert result.unverifiable_attributes is not None
    assert len(result.unverifiable_attributes) == 1
    assert result.unverifiable_attributes[0]["field"] == "connector"
    assert result.unverifiable_attributes[0]["claimed"] == "Lightning"
    assert result.conflicts == []


def test_provenance_chain_tamper_resistance_and_distinct_hashes(catalog):
    from evidence.provenance import verify_provenance_chain, build_provenance_trail
    from datetime import datetime, timezone

    intent = UserIntent(
        id="intent_hash_test",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5"},
        soft_preferences={"color": "black"},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    trail = build_provenance_trail(
        transaction_id="tx_chain_4events_test",
        intent=intent,
        catalog=catalog,
        selected_sku="ELEC-SONY-WH1000XM5-BLK",
    )

    assert len(trail) == 4
    # Confirm every event has a strictly unique hash and correct linkage
    hashes = [e["event_hash"] for e in trail]
    assert len(set(hashes)) == 4, f"Duplicate hashes found: {hashes}"

    # Confirm correct sequential linkage
    assert trail[0]["prev_hash"] == "genesis"
    assert trail[1]["prev_hash"] == trail[0]["event_hash"]
    assert trail[2]["prev_hash"] == trail[1]["event_hash"]
    assert trail[3]["prev_hash"] == trail[2]["event_hash"]

    # Verify clean chain passes
    valid, err = verify_provenance_chain(trail)
    assert valid is True
    assert err is None

    # Test 1: Tampered payload
    corrupted_trail_payload = [dict(e) for e in trail]
    corrupted_trail_payload[1] = dict(corrupted_trail_payload[1])
    corrupted_trail_payload[1]["payload"] = {"tampered": True}
    val_payload, err_payload = verify_provenance_chain(corrupted_trail_payload)
    assert val_payload is False
    assert "Tampered event payload" in err_payload

    # Test 2: Broken linkage
    corrupted_trail_linkage = [dict(e) for e in trail]
    corrupted_trail_linkage[2] = dict(corrupted_trail_linkage[2])
    corrupted_trail_linkage[2]["prev_hash"] = "fake_hash_123"
    val_link, err_link = verify_provenance_chain(corrupted_trail_linkage)
    assert val_link is False
    assert "Broken chain linkage" in err_link


