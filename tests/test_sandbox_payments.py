"""
Tests for Step 5 Sandbox Payment Flows & Card Rail Execution.
Validates test order generation, card token capture, hold transitions, and cryptographic receipt minting.
"""

from unittest.mock import patch, MagicMock
import pytest

from payments.razorpay_client import (
    create_test_order,
    simulate_sandbox_payment_capture,
    generate_sandbox_receipt,
    create_payment_hold,
    capture_payment_hold,
    void_payment_hold,
    clear_payment_holds,
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
    assert order["id"].startswith("order_test_")


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


def test_hold_capture_lifecycle():
    """Validates the two-phase pre-auth hold lifecycle from authorization to post-review capture."""
    hold = create_payment_hold(amount=9999.0, transaction_id="tx_hold_01")
    assert hold["status"] == "authorized"
    assert hold["razorpay_order_id"] is None

    cap = capture_payment_hold(hold_id=hold["hold_id"], transaction_id="tx_hold_01")
    assert cap["status"] == "captured"
    assert cap["razorpay_order_id"] is not None
    assert cap["razorpay_order_id"].startswith("order_")


def test_hold_void_lifecycle():
    """Validates that denied holds are voided without generating debit orders."""
    hold = create_payment_hold(amount=5000.0, transaction_id="tx_void_01")
    voided = void_payment_hold(hold_id=hold["hold_id"], reason="operator_denied")
    assert voided["status"] == "voided"
    assert voided["reason"] == "operator_denied"
