"""
SpendGuard Model Context Protocol (MCP) Server.
Exposes SpendGuard's Four-Pillar AI Trust Gate as a standard MCP tool for Claude Desktop, Cursor, Antigravity, and any MCP-compatible agent host.
"""

import os
import sys
import uuid
from typing import Optional, Dict, Any
from datetime import datetime, timezone

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer  # Fallback for mcp 1.x
    except ImportError:
        MCPServer = None  # type: ignore

from ..client import SpendGuardClient
from ..models import TransactionRequest
from ..exceptions import SpendGuardConnectionError, SpendGuardAPIError, SpendGuardError


def create_mcp_server(
    client: Optional[SpendGuardClient] = None,
    server_name: str = "SpendGuard-AI-Trust-Gate",
) -> Any:
    """
    Creates and configures an MCP server exposing SpendGuard trust gate evaluation tools.
    """
    if MCPServer is None:
        raise RuntimeError("The 'mcp' package is required to run the SpendGuard MCP server. Run 'pip install mcp'.")

    server = MCPServer(server_name)
    sg_client = client or SpendGuardClient(
        base_url=os.environ.get("SPENDGUARD_API_URL", "http://localhost:8000"),
        api_key=os.environ.get("SPENDGUARD_API_KEY", "sg_dev_local_key"),
    )

    @server.tool(
        name="evaluate_transaction",
        description=(
            "Evaluates a proposed autonomous purchase through the SpendGuard AI Trust Gate "
            "(Authority, Intent Fidelity, Evidence Verification, and Behavioral Risk). "
            "Returns whether the purchase is APPROVED, HELD FOR HUMAN VERIFICATION, or BLOCKED "
            "with exact policy, budget, or hardware discrepancy details."
        ),
    )
    def evaluate_transaction(
        sku: str,
        amount: float,
        merchant: str,
        category: str = "electronics",
        brand: Optional[str] = None,
        model: Optional[str] = None,
        claimed_specs: Optional[Dict[str, Any]] = None,
        mandate_id: Optional[str] = "mandate_shop_enterprise",
        user_intent_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> str:
        """
        Executes real-time transaction verification against SpendGuard trust gates.
        Enforces strict fail-closed security.
        """
        tx_id = f"tx_mcp_{uuid.uuid4().hex[:8]}"
        resolved_agent_id = agent_id or f"mcp_agent_{uuid.uuid4().hex[:6]}"
        intent_id = user_intent_id or f"intent_mcp_{tx_id}"

        claimed = {
            "sku": sku,
            "brand": brand or "",
            "model": model or "",
            "category": category,
            "specs": claimed_specs or {},
        }

        tx = TransactionRequest(
            id=tx_id,
            agent_id=resolved_agent_id,
            mandate_id=mandate_id or "mandate_shop_enterprise",
            user_intent_id=intent_id,
            claimed_product=claimed,
            actual_sku=sku,
            amount=float(amount),
            category=category,
            merchant=merchant,
            timestamp=datetime.now(timezone.utc),
            scenario_type="clean_baseline",
            expected_decision="ALLOW",
        )

        try:
            receipt = sg_client.evaluate(tx)
        except SpendGuardConnectionError as err:
            return (
                f"BLOCKED (SECURITY FAIL-CLOSED): SpendGuard Trust Gateway is unreachable ({err}). "
                "The transaction was blocked because corporate security policies cannot be verified offline."
            )
        except SpendGuardAPIError as err:
            return (
                f"BLOCKED (SECURITY FAIL-CLOSED): SpendGuard Trust Gateway returned API error (HTTP {err.status_code}: {err}). "
                "The transaction was blocked."
            )
        except Exception as err:
            return f"BLOCKED (SECURITY FAIL-CLOSED): Unexpected verification error ({err})."

        # Format natural language observation for LLM agent reasoning
        summary_text = f"\nSummary: {receipt.summary}" if receipt.summary else ""
        if receipt.is_allowed:
            order_info = f" Razorpay Order ID: {receipt.razorpay_order_id}." if receipt.razorpay_order_id else ""
            return (
                f"APPROVED: Purchase of {sku} for ₹{amount:,.2f} at {merchant} authorized by SpendGuard Trust Gateway."
                f"{order_info} All 4 trust pillars passed.{summary_text} You may inform the user the purchase succeeded."
            )
        elif receipt.is_verification_required:
            hold_info = f" (Hold ID: {receipt.payment_hold_id})" if receipt.payment_hold_id else ""
            return (
                f"HELD FOR HUMAN VERIFICATION: Purchase of {sku} requires human operator approval.{hold_info} "
                f"Reason: {receipt.decision_reason}.{summary_text} Inform the user that the order is pending compliance review."
            )
        else:  # is_blocked
            return (
                f"BLOCKED: Purchase of {sku} was rejected by SpendGuard Trust Gateway. "
                f"Reason: {receipt.decision_reason}.{summary_text} "
                "You must select a compliant alternative product that satisfies corporate policies or abort."
            )

    return server


def main():
    """Main CLI entrypoint to start SpendGuard MCP server over stdio."""
    server = create_mcp_server()
    print("SpendGuard MCP Server running on stdio transport...", file=sys.stderr)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
