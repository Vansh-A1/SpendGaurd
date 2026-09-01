"""
SpendGuard Native Function-Calling Schemas for OpenAI and Anthropic.
Provides framework-agnostic JSON tool definitions and execution handlers for raw LLM API tool calling without LangChain.
"""

import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from ..client import SpendGuardClient
from ..models import TransactionRequest
from ..exceptions import SpendGuardConnectionError, SpendGuardAPIError


# ------------------------------------------------------------------------------
# 1. Native OpenAI Function-Calling Tool Schema
# ------------------------------------------------------------------------------

OPENAI_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "spendguard_checkout",
        "description": (
            "Submits a proposed purchase to the SpendGuard Corporate Trust Gateway for real-time "
            "policy, spec verification, budget ceiling, and fraud checks. Always call this tool "
            "to finalize and pay for an item. Returns whether the transaction is APPROVED, "
            "HELD FOR HUMAN VERIFICATION, or BLOCKED with specific reasons."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": "Unique product SKU code to purchase."
                },
                "amount": {
                    "type": "number",
                    "description": "Total purchase amount in INR."
                },
                "merchant": {
                    "type": "string",
                    "description": "Seller or merchant name (e.g. 'Dell Official Store', 'Amazon')."
                },
                "category": {
                    "type": "string",
                    "description": "Product category (e.g. 'electronics', 'furniture'). Default: 'electronics'.",
                    "default": "electronics"
                },
                "brand": {
                    "type": "string",
                    "description": "Product brand (e.g. 'Dell', 'Sony', 'Lenovo')."
                },
                "model": {
                    "type": "string",
                    "description": "Product model name."
                },
                "claimed_specs": {
                    "type": "object",
                    "description": "Key hardware / product specifications claimed in listing (e.g. ram_gb, storage_gb, cpu).",
                    "additionalProperties": True
                },
                "notes": {
                    "type": "string",
                    "description": "Procurement reasoning or justification notes for this purchase."
                }
            },
            "required": ["sku", "amount", "merchant"],
            "additionalProperties": False
        }
    }
}


# ------------------------------------------------------------------------------
# 2. Native Anthropic (Claude) Tool Schema
# ------------------------------------------------------------------------------

ANTHROPIC_TOOL_SCHEMA: Dict[str, Any] = {
    "name": "spendguard_checkout",
    "description": (
        "Submits a proposed purchase to the SpendGuard Corporate Trust Gateway for real-time "
        "policy, spec verification, budget ceiling, and fraud checks. Always call this tool "
        "to finalize and pay for an item. Returns whether the transaction is APPROVED, "
        "HELD FOR HUMAN VERIFICATION, or BLOCKED with specific reasons."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "sku": {
                "type": "string",
                "description": "Unique product SKU code to purchase."
            },
            "amount": {
                "type": "number",
                "description": "Total purchase amount in INR."
            },
            "merchant": {
                "type": "string",
                "description": "Seller or merchant name (e.g. 'Dell Official Store', 'Amazon')."
            },
            "category": {
                "type": "string",
                "description": "Product category (e.g. 'electronics', 'furniture'). Default: 'electronics'.",
                "default": "electronics"
            },
            "brand": {
                "type": "string",
                "description": "Product brand (e.g. 'Dell', 'Sony', 'Lenovo')."
            },
            "model": {
                "type": "string",
                "description": "Product model name."
            },
            "claimed_specs": {
                "type": "object",
                "description": "Key hardware / product specifications claimed in listing (e.g. ram_gb, storage_gb, cpu).",
                "additionalProperties": True
            },
            "notes": {
                "type": "string",
                "description": "Procurement reasoning or justification notes for this purchase."
            }
        },
        "required": ["sku", "amount", "merchant"],
        "additionalProperties": False
    }
}


def get_openai_tool_schema() -> Dict[str, Any]:
    """Returns the native JSON tool schema for OpenAI function-calling."""
    return OPENAI_TOOL_SCHEMA


def get_anthropic_tool_schema() -> Dict[str, Any]:
    """Returns the native JSON tool schema for Anthropic Claude function-calling."""
    return ANTHROPIC_TOOL_SCHEMA


def execute_native_checkout(
    tool_arguments: Dict[str, Any],
    client: Optional[SpendGuardClient] = None,
    agent_id: Optional[str] = None,
    mandate_id: Optional[str] = "mandate_shop_enterprise",
    user_intent_id: Optional[str] = None,
) -> str:
    """
    Executes a native tool call against the SpendGuard Trust Gate and returns
    a formatted natural language observation for the LLM agent.
    
    Enforces strict Fail-Closed security: if the gateway is unreachable, returns a BLOCKED observation.
    """
    sg_client = client or SpendGuardClient()
    tx_id = f"tx_native_{uuid.uuid4().hex[:8]}"
    resolved_agent_id = agent_id or f"native_agent_{uuid.uuid4().hex[:6]}"
    intent_id = user_intent_id or f"intent_native_{tx_id}"

    sku = tool_arguments.get("sku", "")
    amount = float(tool_arguments.get("amount", 0.0))
    merchant = tool_arguments.get("merchant", "")
    category = tool_arguments.get("category", "electronics")
    brand = tool_arguments.get("brand", "")
    model = tool_arguments.get("model", "")
    claimed_specs = tool_arguments.get("claimed_specs", {})

    claimed = {
        "sku": sku,
        "brand": brand,
        "model": model,
        "category": category,
        "specs": claimed_specs,
    }

    tx = TransactionRequest(
        id=tx_id,
        agent_id=resolved_agent_id,
        mandate_id=mandate_id or "mandate_shop_enterprise",
        user_intent_id=intent_id,
        claimed_product=claimed,
        actual_sku=sku,
        amount=amount,
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
            "The transaction was blocked because security policies cannot be verified offline."
        )
    except SpendGuardAPIError as err:
        return (
            f"BLOCKED (SECURITY FAIL-CLOSED): SpendGuard Trust Gateway returned an error (HTTP {err.status_code}: {err}). "
            "The transaction was blocked."
        )
    except Exception as err:
        return f"BLOCKED (SECURITY FAIL-CLOSED): Unexpected verification error ({err})."

    # Natural language observation format
    summary_text = f"\nSummary: {receipt.summary}" if receipt.summary else ""
    if receipt.is_allowed:
        settle_parts = []
        if receipt.razorpay_order_id:
            settle_parts.append(f"Order: {receipt.razorpay_order_id}")
        if receipt.razorpay_payment_id:
            settle_parts.append(f"Payment ID: {receipt.razorpay_payment_id}")
        if receipt.settlement_status:
            settle_parts.append(f"Settlement: {receipt.settlement_status}")
        settle_info = f" [{', '.join(settle_parts)}]" if settle_parts else ""
        return (
            f"APPROVED: Purchase of {sku} for ₹{amount:,.2f} at {merchant} authorized and settled by SpendGuard Trust Gateway.{settle_info} "
            f"All 4 trust pillars passed.{summary_text} You may inform the user the purchase succeeded."
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
