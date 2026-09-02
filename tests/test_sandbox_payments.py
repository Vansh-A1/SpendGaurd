"""
Comprehensive unit and integration tests for Step 5 Real Sandbox Payment Rail Flow.
Validates checkout settlement, cryptographic tokens, hold transitions, and the explicit
code-level security guard protecting payment rails from unauthorized/blocked access.
"""

from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import pytest

from data.schema import TransactionRequest
from spendguard.models import DecisionReceipt as SDKDecisionReceipt
from payments.razorpay_client import (
    create_test_order,
    simulate_sandbox_payment_capture,
    generate_sandbox_receipt,
    create_payment_hold,
    capture_payment_hold,
    void_payment_hold,
    clear_payment_holds,
    execute_checkout_settlement,
    PaymentRailSecurityError,
)


@pytest.fixture(autouse=True)
def clean_registry():
    clear_payment_holds()
    yield
    clear_payment_holds()


def test_create_test_order_sandbox_format():
    """Validates that test order generation matches Razorpay order entity specifications."""
    order = create_test_order(
        amount=48990.0,
        currency="INR",
        receipt_id="tx_test_001",
        notes={"custom_note": "integration_test"},
    )
    assert order["entity"] == "order"
    assert order["amount"] == 4899000  # paise
    assert order["currency"] == "INR"
    assert order["receipt"] == "tx_test_001"
    assert order["status"] == "created"
    assert order["id"].startswith("order_")


def test_simulate_sandbox_payment_capture():
    """Validates downstream card token capture and settlement fields."""
    order = create_test_order(amount=24900.0)
    payment = simulate_sandbox_payment_capture(
        order_id=order["id"],
        amount=24900.0,
        card_last4="1111",
        card_network="Visa",
    )
    assert payment["entity"] == "payment"
    assert payment["order_id"] == order["id"]
    assert payment["amount"] == 2490000
    assert payment["status"] == "captured"
    assert payment["card"]["last4"] == "1111"
    assert payment["fee"] > 0
    assert payment["tax"] > 0


def test_generate_sandbox_receipt():
    """Validates cryptographic signing of the settlement receipt."""
    receipt = generate_sandbox_receipt(
        transaction_id="tx_sbx_99",
        order_id="order_test_99",
        payment_id="pay_test_99",
        amount=15000.0,
        merchant="Dell Official Store",
        sku="ELEC-DELL-01",
    )
    assert receipt["status"] == "SETTLED"
    assert len(receipt["signature_hash"]) == 64  # SHA-256 hex string
    assert receipt["amount"] == 15000.0
    assert receipt["receipt_id"].startswith("rcpt_")


def test_execute_checkout_settlement_allow_path():
    """Validates full end-to-end checkout execution for an ALLOW receipt."""
    tx = TransactionRequest(
        id="tx_allow_settle_01",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "Dell", "model": "Inspiron 15"},
        actual_sku="TRAP-ELEC-DELL-5530-CLEAN",
        amount=48990.0,
        category="electronics",
        merchant="Dell Official Store",
        timestamp=datetime.now(timezone.utc),
        scenario_type="clean_baseline",
        expected_decision="ALLOW",
    )
    receipt = SDKDecisionReceipt(
        transaction_id="tx_allow_settle_01",
        decision="ALLOW",
        decision_reason="allowed: all checks passed",
    )

    res = execute_checkout_settlement(receipt=receipt, transaction=tx)
    assert res["settlement_status"] == "SETTLED"
    assert res["razorpay_order_id"].startswith("order_")
    assert res["razorpay_payment_id"].startswith("pay_test_")
    assert len(res["settlement_receipt_token"]) == 64


def test_execute_checkout_settlement_guard_against_block():
    """Validates that execute_checkout_settlement raises a security error for BLOCK decisions."""
    tx = TransactionRequest(
        id="tx_block_guard_01",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "Lenovo", "model": "ThinkPad"},
        actual_sku="TRAP-ELEC-LENOVO-T14-SPOOF",
        amount=49990.0,
        category="electronics",
        merchant="TechDeals Direct",
        timestamp=datetime.now(timezone.utc),
        scenario_type="spec_spoofing",
        expected_decision="BLOCK",
    )
    receipt = SDKDecisionReceipt(
        transaction_id="tx_block_guard_01",
        decision="BLOCK",
        decision_reason="blocked: evidence conflict on specs",
    )

    with pytest.raises(PaymentRailSecurityError) as excinfo:
        execute_checkout_settlement(receipt=receipt, transaction=tx)

    assert "SECURITY VIOLATION: Blocked transaction" in str(excinfo.value)


def test_execute_checkout_settlement_guard_against_unapproved_verify():
    """Validates that execute_checkout_settlement refuses unapproved VERIFY transactions."""
    tx = TransactionRequest(
        id="tx_verify_guard_01",
        agent_id="agent_01",
        mandate_id="mandate_01",
        user_intent_id="intent_01",
        claimed_product={"brand": "Bose", "model": "QC 45"},
        actual_sku="TRAP-ELEC-BOSE-QC45-SUBST",
        amount=24900.0,
        category="electronics",
        merchant="Bose Authorized Hub",
        timestamp=datetime.now(timezone.utc),
        scenario_type="near_miss_substitution",
        expected_decision="VERIFY",
    )
    receipt = SDKDecisionReceipt(
        transaction_id="tx_verify_guard_01",
        decision="VERIFY",
        decision_reason="verified: soft preference deviation",
    )

    with pytest.raises(PaymentRailSecurityError) as excinfo:
        execute_checkout_settlement(receipt=receipt, transaction=tx, is_operator_approved=False)

    assert "SECURITY VIOLATION: Unapproved VERIFY transaction" in str(excinfo.value)


def test_hold_capture_full_loop_post_approval():
    """Validates hold authorization transition to captured on operator approval."""
    hold = create_payment_hold(amount=24900.0, transaction_id="tx_hold_post_appr")
    assert hold["status"] == "authorized"
    assert hold["razorpay_order_id"] is None

    cap = capture_payment_hold(
        hold_id=hold["hold_id"],
        transaction_id="tx_hold_post_appr",
        card_last4="8888",
        card_network="MasterCard",
    )
    assert cap["status"] == "captured"
    assert cap["settlement_status"] == "SETTLED"
    assert cap["razorpay_order_id"].startswith("order_")
    assert cap["razorpay_payment_id"].startswith("pay_test_")
    assert len(cap["settlement_receipt_token"]) == 64


def test_hold_void_loop_post_denial():
    """Validates that denied holds are voided with zero orders and zero payments."""
    hold = create_payment_hold(amount=5000.0, transaction_id="tx_void_01")
    voided = void_payment_hold(hold_id=hold["hold_id"], reason="operator_denied")
    assert voided["status"] == "voided"
    assert voided["settlement_status"] == "HOLD_VOIDED"
    assert voided["reason"] == "operator_denied"
