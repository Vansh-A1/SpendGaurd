"""
Tests for SpendGuard Model Context Protocol (MCP) Server.
Validates tool registration, schema mapping, natural language observations, and fail-closed guarantees.
"""

import asyncio
from unittest.mock import MagicMock
import pytest

from spendguard.integrations.mcp_server import create_mcp_server
from spendguard.models import DecisionReceipt
from spendguard.exceptions import SpendGuardConnectionError, SpendGuardAPIError


@pytest.mark.anyio
async def test_mcp_server_initialization_and_tool_registration():
    """Validates MCP server initialization and evaluate_transaction tool registration."""
    mock_client = MagicMock()
    server = create_mcp_server(client=mock_client)
    assert server is not None
    assert server.name == "SpendGuard-AI-Trust-Gate"
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "evaluate_transaction" in tool_names


@pytest.mark.anyio
async def test_mcp_evaluate_approved_transaction():
    """Validates MCP tool execution on an approved purchase."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_mcp_allow_01",
        decision="ALLOW",
        decision_reason="allowed: all 4 trust pillars passed",
        razorpay_order_id="order_mcp_9988",
    )

    server = create_mcp_server(client=mock_client)
    res = await server.call_tool("evaluate_transaction", {
        "sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "amount": 48990.0,
        "merchant": "Dell Official Store",
        "brand": "Dell",
        "model": "Inspiron 15 5530",
    })
    output = res.content[0].text
    assert "APPROVED:" in output
    assert "Dell Official Store" in output
    assert "order_mcp_9988" in output
    assert "All 4 trust pillars passed" in output


@pytest.mark.anyio
async def test_mcp_evaluate_verify_transaction():
    """Validates MCP tool execution on a verification hold."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_mcp_verify_01",
        decision="VERIFY",
        decision_reason="held for verification: soft preferences mismatch (color)",
        payment_hold_id="hold_mcp_12345",
    )

    server = create_mcp_server(client=mock_client)
    res = await server.call_tool("evaluate_transaction", {
        "sku": "TRAP-ELEC-SONY-XM5-SUBST",
        "amount": 29990.0,
        "merchant": "Sony Center",
        "brand": "Sony",
    })
    output = res.content[0].text
    assert "HELD FOR HUMAN VERIFICATION:" in output
    assert "hold_mcp_12345" in output
    assert "soft preferences mismatch" in output


@pytest.mark.anyio
async def test_mcp_evaluate_blocked_transaction():
    """Validates MCP tool execution on a blocked transaction."""
    mock_client = MagicMock()
    mock_client.evaluate.return_value = DecisionReceipt(
        transaction_id="tx_mcp_block_01",
        decision="BLOCK",
        decision_reason="blocked: evidence conflict on hard requirement (ram_gb, storage_gb)",
    )

    server = create_mcp_server(client=mock_client)
    res = await server.call_tool("evaluate_transaction", {
        "sku": "TRAP-ELEC-LENOVO-T14-SPOOF",
        "amount": 49990.0,
        "merchant": "TechDeals Direct",
        "brand": "Lenovo",
        "claimed_specs": {"ram_gb": 32, "storage_gb": 1024},
    })
    output = res.content[0].text
    assert "BLOCKED:" in output
    assert "evidence conflict on hard requirement" in output


@pytest.mark.anyio
async def test_mcp_evaluate_fail_closed_on_connection_error():
    """
    CRITICAL MCP SECURITY CONTRACT: FAIL-CLOSED.
    If SpendGuard API is unreachable, the MCP tool returns a BLOCKED (SECURITY FAIL-CLOSED) observation.
    """
    mock_client = MagicMock()
    mock_client.evaluate.side_effect = SpendGuardConnectionError(
        "Connection refused by SpendGuard at http://localhost:8000"
    )

    server = create_mcp_server(client=mock_client)
    res = await server.call_tool("evaluate_transaction", {
        "sku": "TRAP-ELEC-DELL-5530-CLEAN",
        "amount": 48990.0,
        "merchant": "Dell Official Store",
    })
    output = res.content[0].text
    assert "BLOCKED (SECURITY FAIL-CLOSED):" in output
    assert "SpendGuard Trust Gateway is unreachable" in output
