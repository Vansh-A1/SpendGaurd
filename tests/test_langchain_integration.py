"""
Tests for SpendGuard LangChain Integration Tool (SpendGuardCheckoutTool).
Validates tool schema, natural language observations, fail-closed handling, and LangChain tool invocation.
"""

from unittest.mock import MagicMock
import pytest

from spendguard.integrations.langchain import SpendGuardCheckoutTool, SpendGuardCheckoutInput
from spendguard.models import DecisionReceipt
from spendguard.exceptions import SpendGuardConnectionError, SpendGuardAPIError


def test_langchain_tool_metadata_and_schema():
    """Validates LangChain BaseTool properties and argument schema."""
    tool = SpendGuardCheckoutTool()
    assert tool.name == "spendguard_checkout"
    assert "SpendGuard Corporate Trust Gateway" in tool.description
    assert tool.args_schema == SpendGuardCheckoutInput

    schema = tool.args_schema.model_json_schema()
    assert "sku" in schema["properties"]
    assert "amount" in schema["properties"]
    assert "merchant" in schema["properties"]


def test_langchain_tool_run_approved_observation():
    """Validates natural language observation returned to agent on ALLOW decision."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_test_allow_01",
        decision="ALLOW",
        decision_reason="allowed: all 4 trust pillars passed",
        razorpay_order_id="order_test_9988",
    )

    tool = SpendGuardCheckoutTool(client=mock_client)
    observation = tool.invoke({
        "sku": "ELEC-DELL-G15-4060",
        "amount": 89990.0,
        "merchant": "Dell Official Store",
        "brand": "Dell",
        "model": "G15 5530",
    })

    assert "APPROVED:" in observation
    assert "Dell Official Store" in observation
    assert "order_test_9988" in observation
    assert "All 4 trust pillars passed" in observation
    assert mock_client.evaluate.called


def test_langchain_tool_run_verify_observation():
    """Validates natural language observation returned to agent on VERIFY decision."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_test_verify_01",
        decision="VERIFY",
        decision_reason="held for verification: soft preferences mismatch (color)",
        payment_hold_id="hold_sec_12345",
    )

    tool = SpendGuardCheckoutTool(client=mock_client)
    observation = tool.invoke({
        "sku": "ELEC-BOSE-QC45-BLK",
        "amount": 24900.0,
        "merchant": "Bose Authorized Hub",
        "brand": "Bose",
        "model": "QuietComfort 45",
    })

    assert "HELD FOR VERIFICATION:" in observation
    assert "hold_sec_12345" in observation
    assert "soft preferences mismatch" in observation


def test_langchain_tool_run_blocked_observation():
    """Validates natural language observation returned to agent on BLOCK decision."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_test_block_01",
        decision="BLOCK",
        decision_reason="blocked: evidence conflict on hard requirement (ram_gb, storage_gb)",
    )

    tool = SpendGuardCheckoutTool(client=mock_client)
    observation = tool.invoke({
        "sku": "TRAP-ELEC-THINK-X1-SPOOF",
        "amount": 89900.0,
        "merchant": "Silicon Valley Components",
        "brand": "Lenovo",
        "model": "ThinkPad X1 Carbon Gen 11",
        "claimed_specs": {"ram_gb": 32, "storage_gb": 1000},
    })

    assert "BLOCKED:" in observation
    assert "evidence conflict on hard requirement" in observation
    assert "You must select a compliant alternative" in observation


def test_langchain_tool_fail_closed_on_connection_error():
    """
    CRITICAL CONTRACT: FAIL-CLOSED.
    If SpendGuardClient raises SpendGuardConnectionError, the tool must return a clear
    BLOCKED (SECURITY FAIL-CLOSED) observation to prevent unverified purchases from completing.
    """
    mock_client = MagicMock()
    mock_client.evaluate.side_effect = SpendGuardConnectionError(
        "Connection refused by SpendGuard at http://localhost:8000"
    )

    tool = SpendGuardCheckoutTool(client=mock_client)
    observation = tool.invoke({
        "sku": "ELEC-DELL-G15-4060",
        "amount": 89990.0,
        "merchant": "Dell Official Store",
    })

    assert "BLOCKED (SECURITY FAIL-CLOSED):" in observation
    assert "SpendGuard Trust Gateway is unreachable" in observation
    assert "blocked because security policies cannot be verified offline" in observation
