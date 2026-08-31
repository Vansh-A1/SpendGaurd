"""
Tests for SpendGuard Native Function-Calling Schemas (OpenAI and Anthropic).
Validates schema formats, call-through to SpendGuardClient, natural language observations, and fail-closed handling.
"""

from unittest.mock import MagicMock
import pytest

from spendguard.integrations.native_schemas import (
    OPENAI_TOOL_SCHEMA,
    ANTHROPIC_TOOL_SCHEMA,
    get_openai_tool_schema,
    get_anthropic_tool_schema,
    execute_native_checkout,
)
from spendguard.models import DecisionReceipt
from spendguard.exceptions import SpendGuardConnectionError, SpendGuardAPIError


def test_openai_tool_schema_structure():
    """Validates that OPENAI_TOOL_SCHEMA adheres strictly to OpenAI tool calling format."""
    schema = get_openai_tool_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "spendguard_checkout"
    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert "sku" in params["properties"]
    assert "amount" in params["properties"]
    assert "merchant" in params["properties"]
    assert "claimed_specs" in params["properties"]
    assert "sku" in params["required"]
    assert "amount" in params["required"]
    assert "merchant" in params["required"]


def test_anthropic_tool_schema_structure():
    """Validates that ANTHROPIC_TOOL_SCHEMA adheres strictly to Anthropic Claude tool format."""
    schema = get_anthropic_tool_schema()
    assert schema["name"] == "spendguard_checkout"
    input_schema = schema["input_schema"]
    assert input_schema["type"] == "object"
    assert "sku" in input_schema["properties"]
    assert "amount" in input_schema["properties"]
    assert "merchant" in input_schema["properties"]
    assert "claimed_specs" in input_schema["properties"]
    assert "sku" in input_schema["required"]
    assert "amount" in input_schema["required"]
    assert "merchant" in input_schema["required"]


def test_execute_native_checkout_allow():
    """Validates execution and natural language formatting on ALLOW."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_native_allow_01",
        decision="ALLOW",
        decision_reason="allowed: all 4 trust pillars passed",
        razorpay_order_id="order_native_123",
    )

    args = {
        "sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "amount": 48990.0,
        "merchant": "Dell Official Store",
        "brand": "Dell",
        "model": "Inspiron 15 5530",
    }

    obs = execute_native_checkout(args, client=mock_client)
    assert "APPROVED:" in obs
    assert "Dell Official Store" in obs
    assert "order_native_123" in obs
    assert "All 4 trust pillars passed" in obs
    assert mock_client.evaluate.called


def test_execute_native_checkout_verify():
    """Validates execution and natural language formatting on VERIFY."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_native_verify_01",
        decision="VERIFY",
        decision_reason="held for verification: soft preferences mismatch (color)",
        payment_hold_id="hold_native_9988",
    )

    args = {
        "sku": "TRAP-ELEC-SONY-XM5-SUBST",
        "amount": 29990.0,
        "merchant": "Sony Center",
        "brand": "Sony",
    }

    obs = execute_native_checkout(args, client=mock_client)
    assert "HELD FOR HUMAN VERIFICATION:" in obs
    assert "hold_native_9988" in obs
    assert "soft preferences mismatch" in obs


def test_execute_native_checkout_block():
    """Validates execution and natural language formatting on BLOCK."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_native_block_01",
        decision="BLOCK",
        decision_reason="blocked: evidence conflict on hard requirement (ram_gb, storage_gb)",
    )

    args = {
        "sku": "TRAP-ELEC-LENOVO-T14-SPOOF",
        "amount": 49990.0,
        "merchant": "TechDeals Direct",
        "brand": "Lenovo",
        "claimed_specs": {"ram_gb": 32, "storage_gb": 1024},
    }

    obs = execute_native_checkout(args, client=mock_client)
    assert "BLOCKED:" in obs
    assert "evidence conflict on hard requirement" in obs
    assert "You must select a compliant alternative" in obs


def test_execute_native_checkout_fail_closed_on_connection_error():
    """
    CRITICAL CONTRACT: FAIL-CLOSED.
    If SpendGuard API is unreachable or times out, the native tool handler returns a
    BLOCKED (SECURITY FAIL-CLOSED) observation.
    """
    mock_client = MagicMock()
    mock_client.evaluate.side_effect = SpendGuardConnectionError(
        "Connection refused by SpendGuard at http://localhost:8000"
    )

    args = {
        "sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "amount": 48990.0,
        "merchant": "Dell Official Store",
    }

    obs = execute_native_checkout(args, client=mock_client)
    assert "BLOCKED (SECURITY FAIL-CLOSED):" in obs
    assert "SpendGuard Trust Gateway is unreachable" in obs
    assert "cannot be verified offline" in obs
