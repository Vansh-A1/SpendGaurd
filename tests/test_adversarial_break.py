"""
SpendGuard Adversarial Security Break-Testing Suite
Validates system resistance against gate bypasses, race conditions, replays, spec disguises,
type/numeric exploits, identity spoofing, and price discrepancies.
"""

import time
import pytest
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient

from api.main import app
from data.schema import TransactionRequest, Product
from session.manager import create_session, clear_sessions


@pytest.fixture
def test_client():
    return TestClient(app)


def test_race_condition_on_session_budget(test_client):
    """
    Vulnerability 1: Concurrency on Session Budget.
    Ensure multiple concurrent transactions under a single session cannot collectively exceed the declared budget cap.
    """
    clear_sessions()
    session_id = f"sess_race_test_{int(time.time() * 1000)}"
    create_session(
        session_id=session_id,
        intent_id="intent_corp_clean_dell",
        agent_id="sim_shopping_agent_01",
        declared_item_count=5,
        declared_total_budget=50000.0,
    )

    def fire_tx(idx):
        req = {
            "id": f"tx_race_{idx}_{int(time.time() * 1000)}_{idx}",
            "agent_id": "sim_shopping_agent_01",
            "mandate_id": "mandate_shop_enterprise",
            "user_intent_id": "intent_corp_clean_dell",
            "session_id": session_id,
            "amount": 48990.0,
            "category": "electronics",
            "merchant": "Dell Official Store",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
            "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0, "color": "platinum silver"},
        }
        resp = test_client.post("/transactions/evaluate", json=req)
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fire_tx, i) for i in range(5)]
        results = [f.result() for f in futures]

    allowed = [r for r in results if r[1].get("decision") == "ALLOW"]
    assert len(allowed) <= 1, f"Expected at most 1 allowed transaction under 50k cap, got {len(allowed)}"


def test_replay_attack_duplicate_rejection(test_client):
    """
    Vulnerability 2: Replay Attack.
    Ensure that submitting an already evaluated/recorded transaction ID returns HTTP 409 Conflict.
    """
    tx_id = f"tx_replay_unit_{int(time.time() * 1000)}"
    req = {
        "id": tx_id,
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 48990.0,
        "category": "electronics",
        "merchant": "Dell Official Store",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0, "color": "platinum silver"},
    }

    resp1 = test_client.post("/transactions/evaluate", json=req)
    assert resp1.status_code == 200

    resp2 = test_client.post("/transactions/evaluate", json=req)
    assert resp2.status_code == 409
    assert "Replay" in resp2.json().get("detail", "")


def test_evidence_field_name_smuggling(test_client):
    """
    Vulnerability 3: Evidence Field-Name Smuggling.
    Ensure spoofed specs under alias keys ('system_memory_gb', 'storage_drive_size') are canonicalized and blocked.
    """
    req = {
        "id": f"tx_smuggle_{int(time.time() * 1000)}",
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 48990.0,
        "category": "electronics",
        "merchant": "Dell Official Store",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {
            "brand": "Dell",
            "model": "Inspiron 15 5530",
            "specs": {
                "system_memory_gb": 128,
                "main_ram_capacity": "128GB",
                "storage_drive_size": 4096,
            }
        }
    }
    resp = test_client.post("/transactions/evaluate", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCK"
    assert "evidence conflict on hard requirement" in data["decision_reason"]


def test_numeric_and_type_edge_cases(test_client):
    """
    Vulnerability 4: Numeric / Type Edge Cases.
    Ensure negative, zero, excessive magnitude, and non-numeric amounts are strictly rejected by validation.
    """
    base_req = {
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "category": "electronics",
        "merchant": "Dell Official Store",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0},
    }

    # Negative amount
    req_neg = dict(base_req, id=f"tx_neg_{time.time()}", amount=-500.0)
    assert test_client.post("/transactions/evaluate", json=req_neg).status_code == 422

    # Zero amount
    req_zero = dict(base_req, id=f"tx_zero_{time.time()}", amount=0.0)
    assert test_client.post("/transactions/evaluate", json=req_zero).status_code == 422

    # Overflow amount
    req_overflow = dict(base_req, id=f"tx_over_{time.time()}", amount=1e15)
    assert test_client.post("/transactions/evaluate", json=req_overflow).status_code == 422

    # Non-numeric string
    req_str = dict(base_req, id=f"tx_str_{time.time()}", amount="fifty thousand")
    assert test_client.post("/transactions/evaluate", json=req_str).status_code == 422


def test_mandate_agent_identity_spoofing(test_client):
    """
    Vulnerability 5: Mandate / Agent Identity Spoofing.
    Ensure presenting a mandate assigned to another agent or a nonexistent mandate is blocked.
    """
    # Mismatched agent
    req_spoof = {
        "id": f"tx_spoof_agent_{int(time.time() * 1000)}",
        "agent_id": "rogue_bot_99",
        "mandate_id": "mandate_shop_enterprise", # assigned to sim_shopping_agent_01
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 48990.0,
        "category": "electronics",
        "merchant": "Dell Official Store",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0},
    }
    resp_spoof = test_client.post("/transactions/evaluate", json=req_spoof)
    assert resp_spoof.status_code == 200
    assert resp_spoof.json()["decision"] == "BLOCK"
    assert "agent_mandate_mismatch" in resp_spoof.json()["decision_reason"]

    # Nonexistent mandate
    req_nonexist = dict(req_spoof, id=f"tx_nonexist_{time.time()}", mandate_id="mandate_nonexistent_999")
    resp_nonexist = test_client.post("/transactions/evaluate", json=req_nonexist)
    assert resp_nonexist.status_code == 404


def test_duplicate_sku_inconsistent_claimed_price(test_client):
    """
    Vulnerability 6: Duplicate SKU, Inconsistent Claimed Price.
    Ensure claiming a false price for a known catalog SKU is blocked as a hard evidence conflict.
    """
    req_cheap = {
        "id": f"tx_cheap_{int(time.time() * 1000)}",
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 12000.0, # Claimed ₹12,000 for ₹48,990 SKU
        "category": "electronics",
        "merchant": "Dell Official Store",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 12000.0},
    }
    resp = test_client.post("/transactions/evaluate", json=req_cheap)
    assert resp.status_code == 200
    data = resp.json()
    assert data["decision"] == "BLOCK"
    assert "evidence conflict on hard requirement (price)" in data["decision_reason"]


def test_merchant_whitelist_homoglyph_and_normalization(test_client):
    """
    Round 2 Vector 1: Merchant Whitelist Homoglyphs and Normalization.
    """
    base_req = {
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 48990.0,
        "category": "electronics",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0},
    }

    # Cyrillic homoglyph should NOT match whitelist
    req_homo = dict(base_req, id=f"tx_homo_{time.time()}", merchant="Dell \u041effiсial Stоre")
    res_homo = test_client.post("/transactions/evaluate", json=req_homo)
    assert res_homo.status_code == 200
    assert res_homo.json()["decision"] == "BLOCK"
    assert "merchant_not_allowed" in res_homo.json()["decision_reason"]

    # Lowercase and padded whitespace should normalize and match
    req_norm = dict(base_req, id=f"tx_norm_{time.time()}", merchant="  dell official store  ")
    res_norm = test_client.post("/transactions/evaluate", json=req_norm)
    assert res_norm.status_code == 200
    assert "merchant_not_allowed" not in res_norm.json()["decision_reason"]


def test_unknown_field_injection_rejection(test_client):
    """
    Round 2 Vector 3: Unknown Field Injection.
    """
    req_injected = {
        "id": f"tx_inj_{time.time()}",
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 48990.0,
        "category": "electronics",
        "merchant": "Dell Official Store",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0},
        "is_admin": True,
        "decision_override": "ALLOW",
        "risk_score": 0.0,
    }
    res = test_client.post("/transactions/evaluate", json=req_injected)
    assert res.status_code == 422


def test_timestamp_drift_and_backdating_protection(test_client):
    """
    Round 2 Vector 4: Timestamp Manipulation Protection.
    """
    base_req = {
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 48990.0,
        "category": "electronics",
        "merchant": "Dell Official Store",
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0},
    }

    # Far future timestamp (> 24 hours)
    req_future = dict(base_req, id=f"tx_fut_{time.time()}", timestamp="2099-01-01T00:00:00Z")
    res_future = test_client.post("/transactions/evaluate", json=req_future)
    assert res_future.status_code == 200
    assert res_future.json()["decision"] == "BLOCK"
    assert "timestamp_future_drift_exceeded" in res_future.json()["authorization"]["failed_checks"]

    # Ancient backdated timestamp (predating mandate creation)
    req_past = dict(base_req, id=f"tx_past_{time.time()}", timestamp="2020-01-01T00:00:00Z")
    res_past = test_client.post("/transactions/evaluate", json=req_past)
    assert res_past.status_code == 200
    assert res_past.json()["decision"] == "BLOCK"
    assert "timestamp_predates_mandate_issuance" in res_past.json()["authorization"]["failed_checks"]


def test_injection_strings_and_oversized_payloads(test_client):
    """
    Round 2 Vector 5: Injection Strings and Oversized Payloads.
    """
    base_req = {
        "agent_id": "sim_shopping_agent_01",
        "mandate_id": "mandate_shop_enterprise",
        "user_intent_id": "intent_corp_clean_dell",
        "amount": 48990.0,
        "category": "electronics",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0},
    }

    # SQL Injection string
    req_sqli = dict(base_req, id=f"tx_sqli_{time.time()}", merchant="Dell Official Store'; DROP TABLE transactions; --")
    res_sqli = test_client.post("/transactions/evaluate", json=req_sqli)
    assert res_sqli.status_code == 200
    assert res_sqli.json()["decision"] == "BLOCK"

    # Oversized payload (> 512 chars)
    req_over = dict(base_req, id=f"tx_over_{time.time()}", merchant="Dell " + "A" * 15000)
    res_over = test_client.post("/transactions/evaluate", json=req_over)
    assert res_over.status_code == 422


def test_burst_rate_limiting(test_client):
    """
    Round 2 Vector 7: Burst Rate-Limiting.
    """
    from api.main import clear_burst_rate_limits
    clear_burst_rate_limits()

    agent_id = f"agent_burst_unit_{int(time.time()*1000)}"
    status_codes = []
    for i in range(45):
        req = {
            "id": f"tx_burst_unit_{i}_{time.time()}_{i}",
            "agent_id": agent_id,
            "mandate_id": "mandate_shop_enterprise",
            "user_intent_id": "intent_corp_clean_dell",
            "amount": 48990.0,
            "category": "electronics",
            "merchant": "Dell Official Store",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actual_sku": "TRAP-ELEC-DELL-5530-CLEAN",
            "claimed_product": {"brand": "Dell", "model": "Inspiron 15 5530", "price": 48990.0},
        }
        res = test_client.post("/transactions/evaluate", json=req)
        status_codes.append(res.status_code)

    assert 429 in status_codes
    assert status_codes.count(429) >= 5
    clear_burst_rate_limits()

