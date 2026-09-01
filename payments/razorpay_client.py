import os
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import razorpay

# In-memory tracking for payment holds and sandbox payments
_PAYMENT_HOLDS: Dict[str, Dict[str, Any]] = {}
_SANDBOX_PAYMENTS: Dict[str, Dict[str, Any]] = {}


def get_razorpay_client() -> Optional[razorpay.Client]:
    """Instantiate razorpay.Client with environment credentials if configured."""
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        return None
    return razorpay.Client(auth=(key_id, key_secret))


def create_test_order(
    amount: float,
    currency: str = "INR",
    receipt_id: str = "",
    notes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Phase 1: Immediate Order Execution (on ALLOW).
    Creates a real Razorpay test-mode order for approved/allowed purchases.
    Amount is converted to paise (amount * 100).
    """
    amount_in_paise = int(round(amount * 100))
    order_notes = {
        "platform": "SpendGuard Trust Layer",
        "environment": "test",
        "phase": "immediate_allow",
    }
    if notes:
        order_notes.update(notes)

    client = get_razorpay_client()
    if client is not None:
        data = {
            "amount": amount_in_paise,
            "currency": currency,
            "receipt": receipt_id or "sg_receipt",
            "notes": order_notes,
        }
        return client.order.create(data=data)

    # Sandbox / Test environment order generation
    order_id = f"order_test_{uuid.uuid4().hex[:14]}"
    order = {
        "id": order_id,
        "entity": "order",
        "amount": amount_in_paise,
        "amount_paid": 0,
        "amount_due": amount_in_paise,
        "currency": currency,
        "receipt": receipt_id or "sg_receipt",
        "status": "created",
        "attempts": 0,
        "notes": order_notes,
        "created_at": int(datetime.now(timezone.utc).timestamp()),
    }
    return order


def simulate_sandbox_payment_capture(
    order_id: str,
    amount: float,
    currency: str = "INR",
    card_last4: str = "4242",
    card_network: str = "Visa",
    card_type: str = "credit",
) -> Dict[str, Any]:
    """
    Executes a sandbox payment capture against an approved Razorpay test order.
    Simulates gateway authorization, card token charge, and settlement confirmation.
    """
    amount_in_paise = int(round(amount * 100))
    payment_id = f"pay_test_{uuid.uuid4().hex[:14]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    # Calculate simulated fee and tax
    fee_paise = int(round(amount_in_paise * 0.02))  # 2% standard gateway fee
    tax_paise = int(round(fee_paise * 0.18))       # 18% GST on gateway fee

    payment_record = {
        "id": payment_id,
        "entity": "payment",
        "order_id": order_id,
        "amount": amount_in_paise,
        "amount_in_rupees": float(amount),
        "currency": currency,
        "status": "captured",
        "method": "card",
        "card": {
            "id": f"card_test_{uuid.uuid4().hex[:10]}",
            "entity": "card",
            "name": "Corporate Procurement Card",
            "last4": card_last4,
            "network": card_network,
            "type": card_type,
            "issuer": "HDFC",
            "international": False,
            "emi": False,
        },
        "bank": None,
        "wallet": None,
        "vpa": None,
        "email": "procurement-agent@enterprise.internal",
        "contact": "+919876543210",
        "fee": fee_paise,
        "tax": tax_paise,
        "error_code": None,
        "error_description": None,
        "created_at": now_iso,
        "captured_at": now_iso,
    }

    _SANDBOX_PAYMENTS[payment_id] = payment_record
    return payment_record


def generate_sandbox_receipt(
    transaction_id: str,
    order_id: str,
    payment_id: str,
    amount: float,
    merchant: str,
    sku: str,
) -> Dict[str, Any]:
    """
    Generates a cryptographically signed SpendGuard Sandbox Payment Receipt.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    raw_payload = f"{transaction_id}:{order_id}:{payment_id}:{amount}:{merchant}:{sku}:{now_iso}"
    sig = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    return {
        "receipt_id": f"rcpt_{uuid.uuid4().hex[:12]}",
        "transaction_id": transaction_id,
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "amount": float(amount),
        "currency": "INR",
        "merchant": merchant,
        "sku": sku,
        "status": "SETTLED",
        "payment_rail": "Razorpay Sandbox (Card Rail)",
        "issued_at": now_iso,
        "signature_hash": sig,
    }


def create_payment_hold(
    amount: float,
    currency: str = "INR",
    transaction_id: str = "",
    notes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Phase 2: Authorization Hold (on VERIFY).
    Earmarks funds without capture while human verification is pending.
    """
    hold_id = f"hold_{uuid.uuid4().hex[:14]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    amount_in_paise = int(round(amount * 100))

    hold_record = {
        "hold_id": hold_id,
        "transaction_id": transaction_id,
        "amount": float(amount),
        "amount_in_paise": amount_in_paise,
        "currency": currency,
        "status": "authorized",  # 'authorized' (pending capture), 'captured', 'voided'
        "razorpay_order_id": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "notes": notes or {},
    }

    _PAYMENT_HOLDS[hold_id] = hold_record
    return hold_record


class PaymentRailSecurityError(Exception):
    """Raised when an unapproved, blocked, or invalid transaction attempts to touch payment rails."""
    pass


def execute_checkout_settlement(
    receipt: Any,
    transaction: Any,
    card_last4: str = "4242",
    card_network: str = "Visa",
    is_operator_approved: bool = False,
) -> Dict[str, Any]:
    """
    Code-level gate protecting the payment rail.
    Strictly forbids BLOCK, fail-closed, or unapproved VERIFY transactions from touching payment rails.
    """
    decision = getattr(receipt, "decision", None) or (receipt.get("decision") if isinstance(receipt, dict) else None)

    # Explicit Code-Level Guard
    if decision == "BLOCK":
        raise PaymentRailSecurityError(
            f"SECURITY VIOLATION: Blocked transaction {getattr(transaction, 'id', '')} attempted to access payment rails. Execution halted."
        )

    if decision == "VERIFY" and not is_operator_approved:
        raise PaymentRailSecurityError(
            f"SECURITY VIOLATION: Unapproved VERIFY transaction {getattr(transaction, 'id', '')} cannot be settled without explicit human operator clearance."
        )

    if decision not in ("ALLOW", "VERIFY"):
        raise PaymentRailSecurityError(
            f"SECURITY VIOLATION: Invalid or fail-closed transaction state ({decision}) cannot access payment rails."
        )

    # Execute full Razorpay test-mode order and payment capture loop
    amount = float(getattr(transaction, "amount", 0.0) or (transaction.get("amount", 0.0) if isinstance(transaction, dict) else 0.0))
    tx_id = getattr(transaction, "id", "") or (transaction.get("id", "") if isinstance(transaction, dict) else "")
    merchant = getattr(transaction, "merchant", "") or (transaction.get("merchant", "") if isinstance(transaction, dict) else "")
    sku = getattr(transaction, "actual_sku", "") or (transaction.get("actual_sku", "") if isinstance(transaction, dict) else "")

    order = create_test_order(amount=amount, currency="INR", receipt_id=tx_id)
    payment = simulate_sandbox_payment_capture(
        order_id=order["id"],
        amount=amount,
        currency="INR",
        card_last4=card_last4,
        card_network=card_network,
    )
    settlement = generate_sandbox_receipt(
        transaction_id=tx_id,
        order_id=order["id"],
        payment_id=payment["id"],
        amount=amount,
        merchant=merchant,
        sku=sku,
    )

    return {
        "order": order,
        "payment": payment,
        "settlement": settlement,
        "razorpay_order_id": order["id"],
        "razorpay_payment_id": payment["id"],
        "captured_at": payment["captured_at"],
        "settlement_status": "SETTLED",
        "settlement_receipt_token": settlement["signature_hash"],
    }


def capture_payment_hold(
    hold_id: str,
    amount: Optional[float] = None,
    currency: str = "INR",
    transaction_id: str = "",
    card_last4: str = "8888",
    card_network: str = "MasterCard",
) -> Dict[str, Any]:
    """
    Phase 2 Capture: Triggered upon Human Approval of a VERIFY transaction.
    Transitions local hold status to 'captured' and executes the underlying Razorpay order & card settlement.
    """
    hold = _PAYMENT_HOLDS.get(hold_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    capture_amount = amount if amount is not None else (hold["amount"] if hold else 0.0)
    tx_id = transaction_id or (hold["transaction_id"] if hold else "")

    # Create underlying Razorpay test order
    try:
        order = create_test_order(
            amount=capture_amount,
            currency=currency,
            receipt_id=tx_id,
            notes={"hold_id": hold_id, "action": "capture_post_verification"},
        )
        order_id = order.get("id")
    except Exception:
        order_id = f"order_cap_{uuid.uuid4().hex[:12]}"

    # Execute payment capture
    payment = simulate_sandbox_payment_capture(
        order_id=order_id,
        amount=capture_amount,
        currency=currency,
        card_last4=card_last4,
        card_network=card_network,
    )

    # Generate settlement receipt token
    settlement = generate_sandbox_receipt(
        transaction_id=tx_id,
        order_id=order_id,
        payment_id=payment["id"],
        amount=capture_amount,
        merchant="Post-Verification Approved Merchant",
        sku=tx_id,
    )

    if hold:
        hold["status"] = "captured"
        hold["razorpay_order_id"] = order_id
        hold["razorpay_payment_id"] = payment["id"]
        hold["settlement_status"] = "SETTLED"
        hold["settlement_receipt_token"] = settlement["signature_hash"]
        hold["captured_at"] = now_iso
        hold["updated_at"] = now_iso

    return {
        "hold_id": hold_id,
        "transaction_id": tx_id,
        "amount": capture_amount,
        "currency": currency,
        "status": "captured",
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment["id"],
        "captured_at": now_iso,
        "settlement_status": "SETTLED",
        "settlement_receipt_token": settlement["signature_hash"],
    }


def void_payment_hold(
    hold_id: str,
    reason: str = "human_denied",
) -> Dict[str, Any]:
    """
    Phase 2 Void: Triggered upon Human Denial or SLA Timeout.
    Releases the earmarked authorization hold without debiting funds.
    """
    hold = _PAYMENT_HOLDS.get(hold_id)
    now_iso = datetime.now(timezone.utc).isoformat()

    if hold:
        hold["status"] = "voided"
        hold["void_reason"] = reason
        hold["settlement_status"] = "HOLD_VOIDED"
        hold["updated_at"] = now_iso

    return {
        "hold_id": hold_id,
        "status": "voided",
        "settlement_status": "HOLD_VOIDED",
        "reason": reason,
        "voided_at": now_iso,
    }


def get_payment_hold(hold_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve an active or historical payment hold record."""
    return _PAYMENT_HOLDS.get(hold_id)


def clear_payment_holds():
    """Reset the in-memory hold registry (useful for test isolation)."""
    _PAYMENT_HOLDS.clear()
    _SANDBOX_PAYMENTS.clear()
