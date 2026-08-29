import os
from typing import Dict, Any, Optional
import razorpay


def get_razorpay_client() -> razorpay.Client:
    """Instantiate razorpay.Client with environment credentials."""
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise ValueError(
            "Razorpay API keys not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in environment."
        )
    return razorpay.Client(auth=(key_id, key_secret))


def create_test_order(
    amount: float,
    currency: str = "INR",
    receipt_id: str = "",
) -> Dict[str, Any]:
    """
    Creates a real Razorpay test-mode order for approved/allowed purchases.
    Amount is converted to paise (amount * 100).
    """
    client = get_razorpay_client()
    amount_in_paise = int(round(amount * 100))

    data = {
        "amount": amount_in_paise,
        "currency": currency,
        "receipt": receipt_id or "sg_receipt",
        "notes": {
            "platform": "SpendGuard Trust Layer",
            "environment": "test",
        },
    }

    order = client.order.create(data=data)
    return order
