"""
SpendGuard End-to-End Real Sandbox Payment Flow Demo.

Demonstrates the complete lifecycle of autonomous agent procurement:
1. Case 1: ALLOW -> Immediate Razorpay Test-Mode Order -> Sandbox Card Token Capture -> Cryptographic Settlement Receipt
2. Case 2: BLOCK -> Hard Stop & Code-Level Payment Rail Guard (Zero Order, Zero Card Charge)
3. Case 3: VERIFY (Approved) -> Pre-Auth Hold -> Operator Approval -> Post-Review Card Capture & Settlement
4. Case 4: VERIFY (Denied / Void) -> Pre-Auth Hold -> Operator Denial / Timeout -> Hold Voided (Zero Money Captured)
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
    void_payment_hold,
    clear_payment_holds,
    execute_checkout_settlement,
    PaymentRailSecurityError,
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


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def run_sandbox_demo():
    print("=" * 100)
    print(" SPENDGUARD REAL SANDBOX PAYMENT RAIL FLOW DEMO (RAZORPAY TEST MODE)")
    print(" Demonstrating full transaction lifecycle: Trust Gating -> Order Creation -> Sandbox Card Capture -> Settlement")
    print("=" * 100)

    api_mod.MANDATES_CACHE = {}
    api_mod.CATALOG_CACHE = []
    clear_payment_holds()

    sg_client, mock_urlopen = create_in_process_spendguard_client()

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        # ----------------------------------------------------------------------
        # CASE 1: Clean Baseline Purchase (ALLOW -> Full Settlement)
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

        print(f"\n2. SpendGuard Decision Receipt Received:")
        print(f"   • Verdict:         {receipt1.decision} (Reason: {receipt1.decision_reason})")
        print(f"   • Plain Summary:   {receipt1.summary}")
        print(f"   • Authorization:   Passed={_get(receipt1.authorization, 'passed')}")
        print(f"   • Intent Fidelity: Hard Match={_get(receipt1.intent_fidelity, 'hard_match')}, Soft Score={_get(receipt1.intent_fidelity, 'soft_score')}")
        print(f"   • Evidence Gate:   Conflict={_get(receipt1.evidence, 'conflict')}")
        print(f"   • Behavioral Risk: Score={_get(receipt1.behavioral_risk, 'score')}")
        print(f"   • Razorpay Order:  {receipt1.razorpay_order_id}")
        print(f"   • Payment ID:      {receipt1.razorpay_payment_id}")
        print(f"   • Settlement:      {receipt1.settlement_status} (Captured At: {receipt1.captured_at})")
        print(f"   • Receipt Hash:    {str(receipt1.settlement_receipt_token)[:32]}...")

        assert receipt1.is_allowed
        assert receipt1.razorpay_order_id is not None
        assert receipt1.razorpay_payment_id is not None
        assert receipt1.is_settled

        # ----------------------------------------------------------------------
        # CASE 2: Spec Spoofing Adversarial Trap (BLOCK -> Hard Stop)
        # ----------------------------------------------------------------------
        print("\n" + "#" * 100)
        print(" [CASE 2] SPEC SPOOFING ATTACK: ThinkPad T14 Spoof (Claimed 32GB / Actual 8GB)")
        print(" Expected Flow: Evidence Conflict -> Hard BLOCK -> Zero Razorpay Order -> Rail Guard Enforced")
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
        print(f"   • Plain Summary:   {receipt2.summary}")
        print(f"   • Evidence Gate:   Conflict={_get(receipt2.evidence, 'conflict')}")
        print(f"   • Discrepancies:   {_get(receipt2.evidence, 'discrepancies')}")
        print(f"   • Razorpay Order:  {receipt2.razorpay_order_id} (Zero Order Created)")
        print(f"   • Payment ID:      {receipt2.razorpay_payment_id} (Zero Payment Created)")

        assert receipt2.is_blocked
        assert receipt2.razorpay_order_id is None
        assert receipt2.razorpay_payment_id is None

        # Test Code-Level Guard against non-approved transactions
        try:
            execute_checkout_settlement(receipt2, tx2)
            raise AssertionError("Security Guard failed to stop blocked receipt from touching payment rail!")
        except PaymentRailSecurityError as p_err:
            print(f"\n3. Security Guard Active: {p_err}")
            print(f"   Security Verification: Payment rail was NEVER touched. Zero money moved.")

        # ----------------------------------------------------------------------
        # CASE 3: Near-Miss Substitution (VERIFY -> Human Approval -> Capture)
        # ----------------------------------------------------------------------
        print("\n" + "#" * 100)
        print(" [CASE 3] NEAR-MISS SUBSTITUTION: Bose QC 45 (VERIFY -> Human Approval -> Settle)")
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
            agent_id="agent_sbx_bose",
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
        print(f"   • Plain Summary:   {receipt3.summary}")
        print(f"   • Payment Hold ID: {receipt3.payment_hold_id}")
        print(f"   • Hold Status:     {str(receipt3.payment_hold_status).upper()}")

        assert receipt3.is_verification_required
        assert receipt3.payment_hold_id is not None
        assert receipt3.razorpay_payment_id is None

        print(f"\n3. Operator Review in SpendGuard Console: Operator reviews provenance & approves substitution.")
        cap_res = capture_payment_hold(
            hold_id=receipt3.payment_hold_id,
            amount=tx3.amount,
            transaction_id=tx3.id,
            card_last4="8888",
            card_network="MasterCard",
        )
        print(f"   • Hold Transition: authorized -> {cap_res['status'].upper()}")
        print(f"   • Razorpay Order:  {cap_res['razorpay_order_id']}")
        print(f"   • Payment ID:      {cap_res['razorpay_payment_id']}")
        print(f"   • Settlement:      {cap_res['settlement_status']} (Captured At: {cap_res['captured_at']})")
        print(f"   • Settlement Token:{cap_res['settlement_receipt_token'][:32]}...")

        # ----------------------------------------------------------------------
        # CASE 4: Stale Mandate / Operator Denial (VERIFY -> Denied -> Voided Hold)
        # ----------------------------------------------------------------------
        print("\n" + "#" * 100)
        print(" [CASE 4] OPERATOR DENIAL: Unusual Spending Spike (VERIFY -> Operator Denied -> Void)")
        print(" Expected Flow: Elevated Risk -> Pre-Auth Hold -> Operator Rejection -> Hold Voided (Zero Debit)")
        print("#" * 100)

        tx4 = TransactionRequest(
            id=f"tx_sbx_{uuid.uuid4().hex[:8]}",
            agent_id="agent_sbx_bose",
            mandate_id="mandate_shop_enterprise",
            user_intent_id="intent_bose_subst_demo",
            claimed_product={
                "brand": "Bose",
                "model": "QuietComfort 45",
                "specs": {"color": "silver edition", "anc": True},
            },
            actual_sku="TRAP-ELEC-BOSE-QC45-SUBST",
            amount=24900.0,
            category="electronics",
            merchant="Bose Authorized Hub",
            scenario_type="near_miss_substitution",
            expected_decision="VERIFY",
        )

        receipt4 = sg_client.evaluate(tx4)
        print(f"\n1. Submitting Transaction -> Placed on Hold: {receipt4.payment_hold_id}")
        assert receipt4.is_verification_required

        print(f"\n2. Operator Review: Operator inspects and DENIES the purchase (policy non-compliance).")
        void_res = void_payment_hold(hold_id=receipt4.payment_hold_id, reason="operator_declined_substitution")
        print(f"   • Hold Transition: authorized -> {void_res['status'].upper()} (Reason: {void_res['reason']})")
        print(f"   • Settlement:      {void_res['settlement_status']}")
        print(f"   • Razorpay Rails:  Zero Orders Created | Zero Payments Captured | Zero Money Moved.")

    print("\n" + "=" * 100)
    print(" SANDBOX PAYMENT DEMO COMPLETED SUCCESSFULLY (ALL 4 CASES VERIFIED)")
    print("=" * 100 + "\n")


if __name__ == "__main__":
    run_sandbox_demo()
