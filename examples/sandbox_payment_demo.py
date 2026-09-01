"""
SpendGuard End-to-End Real Sandbox Payment Flow Demo.

Demonstrates the complete lifecycle of autonomous agent procurement:
1. Agent Proposal -> 4-Pillar Gate Evaluation
2. ALLOW -> Immediate Razorpay Test-Mode Order -> Sandbox Card Token Capture -> Cryptographic Settlement Receipt
3. BLOCK -> Hard Stop (Zero Order, Zero Card Charge)
4. VERIFY -> Pre-Auth Hold -> Human Operator Approval -> Payment Capture & Settlement
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
import api.main as api_mod
from spendguard import SpendGuardClient, TransactionRequest
from payments.razorpay_client import (
    simulate_sandbox_payment_capture,
    generate_sandbox_receipt,
    capture_payment_hold,
    clear_payment_holds,
)


def create_in_process_spendguard_client():
    test_client = TestClient(api_mod.app)
    sg_client = SpendGuardClient(base_url="http://in-process-spendguard.local")

    def mock_urlopen(req, timeout=10.0):
        url = req.full_url
        path = url.replace("http://in-process-spendguard.local", "")
        method = req.get_method()
        headers = dict(req.headers)
        data_bytes = req.data
        json_data = json.loads(data_bytes.decode("utf-8")) if data_bytes else None

        if method == "POST" and path == "/transactions/evaluate":
            resp = test_client.post("/transactions/evaluate", json=json_data)
        elif method == "GET" and path == "/health":
            resp = test_client.get("/health")
        else:
            resp = test_client.get(path)

        mock_resp = MagicMock()
        mock_resp.getcode.return_value = resp.status_code
        mock_resp.read.return_value = resp.content
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    return sg_client, mock_urlopen


def run_sandbox_demo():
    print("=" * 100)
    print(" SPENDGUARD REAL SANDBOX PAYMENT FLOW DEMO (RAZORPAY TEST RAILS)")
    print(" Demonstrating full transaction lifecycle: Trust Gating -> Order Creation -> Sandbox Capture")
    print("=" * 100)

    api_mod.MANDATES_CACHE = {}
    api_mod.CATALOG_CACHE = []
    clear_payment_holds()

    sg_client, mock_urlopen = create_in_process_spendguard_client()

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # ----------------------------------------------------------------------
        # CASE 1: Clean Baseline Purchase (ALLOW -> Order -> Sandbox Capture)
        # ----------------------------------------------------------------------
        print("\n" + "#" * 100)
        print(" [CASE 1] CLEAN BASELINE PURCHASE: Dell Inspiron 15 (₹48,990.00)")
        print(" Expected Flow: 4 Pillars PASS -> Razorpay Order Created -> Sandbox Card Charged -> Settled")
        print("#" * 100)

        tx1 = TransactionRequest(
            id=f"tx_sbx_{uuid.uuid4().hex[:8]}",
            agent_id=f"agent_sbx_{uuid.uuid4().hex[:6]}",
            mandate_id="mandate_shop_enterprise",
            user_intent_id="intent_dell_clean",
            claimed_product={
                "brand": "Dell",
                "model": "Inspiron 15 5530",
                "specs": {"ram_gb": 16, "storage_gb": 512, "cpu": "Intel Core i5-1335U", "color": "platinum silver"},
            },
            actual_sku="TRAP-ELEC-DELL-5530-CLEAN",
            amount=48990.0,
            category="electronics",
            merchant="Dell Official Store",
            scenario_type="clean_baseline",
            expected_decision="ALLOW",
        )

        print(f"\n1. Submitting Transaction to SpendGuard Trust Gateway:\n"
              f"   SKU: {tx1.actual_sku} | Amount: ₹{tx1.amount:,.2f} | Merchant: {tx1.merchant}")

        receipt1 = sg_client.evaluate(tx1)

        def _get(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        print(f"\n2. SpendGuard Decision Receipt Received:")
        print(f"   • Verdict:         {receipt1.decision} (Reason: {receipt1.decision_reason})")
        print(f"   • Authorization:   Passed={_get(receipt1.authorization, 'passed')}")
        print(f"   • Intent Fidelity: Hard Match={_get(receipt1.intent_fidelity, 'hard_match')}, Soft Score={_get(receipt1.intent_fidelity, 'soft_score')}")
        print(f"   • Evidence Gate:   Conflict={_get(receipt1.evidence, 'conflict')}")
        print(f"   • Behavioral Risk: Score={_get(receipt1.behavioral_risk, 'score')}")
        print(f"   • Razorpay Order:  {receipt1.razorpay_order_id}")

        assert receipt1.is_allowed
        assert receipt1.razorpay_order_id is not None

        print(f"\n3. Executing Downstream Sandbox Payment Capture (Card Rail):")
        payment1 = simulate_sandbox_payment_capture(
            order_id=receipt1.razorpay_order_id,
            amount=tx1.amount,
            card_last4="4242",
            card_network="Visa",
        )
        print(f"   • Payment ID:      {payment1['id']}")
        print(f"   • Status:          {payment1['status'].upper()}")
        print(f"   • Card:            {payment1['card']['network']} ending in {payment1['card']['last4']} ({payment1['card']['type']})")
        print(f"   • Gateway Fee/Tax: ₹{payment1['fee']/100:.2f} + ₹{payment1['tax']/100:.2f}")

        receipt_token1 = generate_sandbox_receipt(
            transaction_id=tx1.id,
            order_id=receipt1.razorpay_order_id,
            payment_id=payment1["id"],
            amount=tx1.amount,
            merchant=tx1.merchant,
            sku=tx1.actual_sku,
        )
        print(f"\n4. Cryptographic Settlement Receipt Issued:")
        print(f"   • Receipt ID:      {receipt_token1['receipt_id']}")
        print(f"   • Status:          {receipt_token1['status']}")
        print(f"   • Signature Hash:  {receipt_token1['signature_hash'][:32]}...")

        # ----------------------------------------------------------------------
        # CASE 2: Spec Spoofing Adversarial Trap (BLOCK -> Zero Payment)
        # ----------------------------------------------------------------------
        print("\n" + "#" * 100)
        print(" [CASE 2] SPEC SPOOFING ATTACK: ThinkPad T14 Spoof (Claimed 32GB / Actual 8GB)")
        print(" Expected Flow: Evidence Conflict -> Hard BLOCK -> Zero Razorpay Order -> Zero Payment")
        print("#" * 100)

        tx2 = TransactionRequest(
            id=f"tx_sbx_{uuid.uuid4().hex[:8]}",
            agent_id=f"agent_sbx_{uuid.uuid4().hex[:6]}",
            mandate_id="mandate_shop_enterprise",
            user_intent_id="intent_thinkpad_spoof",
            claimed_product={
                "brand": "Lenovo",
                "model": "ThinkPad T14 Gen 4",
                "specs": {"ram_gb": 32, "storage_gb": 1024, "cpu": "Intel Core i7-1365U", "gpu": "Dedicated Iris Xe"},
            },
            actual_sku="TRAP-ELEC-LENOVO-T14-SPOOF",
            amount=49990.0,
            category="electronics",
            merchant="TechDeals Direct",
            scenario_type="spec_spoofing",
            expected_decision="BLOCK",
        )

        print(f"\n1. Submitting Malicious Transaction to SpendGuard Trust Gateway:\n"
              f"   SKU: {tx2.actual_sku} | Amount: ₹{tx2.amount:,.2f} | Claimed Specs: 32GB RAM / 1TB SSD")

        receipt2 = sg_client.evaluate(tx2)

        print(f"\n2. SpendGuard Decision Receipt Received:")
        print(f"   • Verdict:         {receipt2.decision} (Reason: {receipt2.decision_reason})")
        print(f"   • Evidence Gate:   Conflict={receipt2.evidence.conflict}")
        print(f"   • Razorpay Order:  {receipt2.razorpay_order_id} (Zero Order Created)")

        assert receipt2.is_blocked
        assert receipt2.razorpay_order_id is None
        print(f"\n3. Security Verification: Payment rail was NEVER touched. Zero money moved.")

        # ----------------------------------------------------------------------
        # CASE 3: Near-Miss Substitution (VERIFY -> Pre-Auth Hold -> Approved -> Captured)
        # ----------------------------------------------------------------------
        print("\n" + "#" * 100)
        print(" [CASE 3] NEAR-MISS SUBSTITUTION: Bose QC 45 (VERIFY -> Human Approval -> Capture)")
        print(" Expected Flow: Soft Mismatch -> Pre-Auth Hold -> Operator Approval -> Post-Review Capture")
        print("#" * 100)

        from intent.schema import UserIntent

        intent_bose = UserIntent(
            id="intent_bose_subst_demo",
            agent_id="agent_sbx_bose",
            hard_requirements={"brand": "Bose", "category": "electronics", "max_price": 30000.0},
            soft_preferences={"color": "triple black"},
            substitution_allowed=True,
            created_at=datetime.now(timezone.utc),
        )
        api_mod.INTENTS_CACHE["intent_bose_subst_demo"] = intent_bose

        tx3 = TransactionRequest(
            id=f"tx_sbx_{uuid.uuid4().hex[:8]}",
            agent_id=f"agent_sbx_{uuid.uuid4().hex[:6]}",
            mandate_id="mandate_shop_enterprise",
            user_intent_id="intent_bose_subst_demo",
            claimed_product={
                "brand": "Bose",
                "model": "QuietComfort 45",
                "specs": {"color": "white smoke", "anc": True},
            },
            actual_sku="TRAP-ELEC-BOSE-QC45-SUBST",
            amount=24900.0,
            category="electronics",
            merchant="Bose Authorized Hub",
            scenario_type="near_miss_substitution",
            expected_decision="VERIFY",
        )

        print(f"\n1. Submitting Substitution Transaction to SpendGuard Trust Gateway:\n"
              f"   SKU: {tx3.actual_sku} | Amount: ₹{tx3.amount:,.2f} | Merchant: {tx3.merchant}\n"
              f"   User Preference: 'triple black' | Selected Variant: 'white smoke'")

        receipt3 = sg_client.evaluate(tx3)

        print(f"\n2. SpendGuard Decision Receipt Received:")
        print(f"   • Verdict:         {receipt3.decision} (Reason: {receipt3.decision_reason})")
        print(f"   • Payment Hold ID: {receipt3.payment_hold_id}")
        print(f"   • Hold Status:     {str(receipt3.payment_hold_status).upper()}")

        assert receipt3.is_verification_required
        assert receipt3.payment_hold_id is not None

        print(f"\n3. Operator Review in SpendGuard Console: Operator reviews provenance & approves substitution.")
        capture_res = capture_payment_hold(
            hold_id=receipt3.payment_hold_id,
            amount=tx3.amount,
            transaction_id=tx3.id,
        )
        print(f"   • Hold Transition: {receipt3.payment_hold_status} -> {capture_res['status'].upper()}")
        print(f"   • Razorpay Order:  {capture_res['razorpay_order_id']}")

        payment3 = simulate_sandbox_payment_capture(
            order_id=capture_res["razorpay_order_id"],
            amount=tx3.amount,
            card_last4="8888",
            card_network="MasterCard",
        )
        print(f"   • Payment ID:      {payment3['id']}")
        print(f"   • Payment Status:  {payment3['status'].upper()}")
        print(f"   • Card:            {payment3['card']['network']} ending in {payment3['card']['last4']}")

    print("\n" + "=" * 100)
    print(" SANDBOX PAYMENT DEMO COMPLETED SUCCESSFULLY (ALL 3 CASES VERIFIED)")
    print("=" * 100)


if __name__ == "__main__":
    run_sandbox_demo()
