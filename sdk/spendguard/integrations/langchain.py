"""
SpendGuard LangChain Integration.
Provides SpendGuardCheckoutTool as a drop-in LangChain BaseTool to govern agent purchase decisions.
"""

from typing import Optional, Dict, Any, Type
from datetime import datetime, timezone
import uuid

from pydantic import BaseModel, Field

try:
    from langchain_core.tools import BaseTool
except ImportError:
    # Fallback placeholder if langchain_core is not installed
    class BaseTool:  # type: ignore
        pass

from ..client import SpendGuardClient
from ..models import TransactionRequest
from ..exceptions import SpendGuardConnectionError, SpendGuardAPIError, SpendGuardError


class SpendGuardCheckoutInput(BaseModel):
    """Input schema for SpendGuardCheckoutTool."""
    sku: str = Field(description="The unique product SKU code to purchase.")
    amount: float = Field(description="The total purchase amount in INR.")
    merchant: str = Field(description="The seller or merchant name (e.g., 'Dell Official Store', 'Amazon').")
    category: str = Field(default="electronics", description="The product category (e.g., 'electronics', 'furniture').")
    brand: Optional[str] = Field(default=None, description="The product brand (e.g., 'Dell', 'Sony', 'Apple').")
    model: Optional[str] = Field(default=None, description="The product model name.")
    claimed_specs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Key product specs claimed by listing (e.g. ram_gb, storage_gb).")
    notes: Optional[str] = Field(default="", description="Procurement reasoning or justification for this purchase.")
    agent_id: Optional[str] = Field(default="langchain_procurement_agent", description="The agent identifier.")
    mandate_id: Optional[str] = Field(default="mandate_shop_enterprise", description="The corporate mandate ID governing this transaction.")
    user_intent_id: Optional[str] = Field(default=None, description="The user intent reference ID.")


class SpendGuardCheckoutTool(BaseTool):
    """
    LangChain Tool that submits proposed purchases to the SpendGuard AI Trust Gate.
    
    Returns structured natural language observations explaining whether the purchase
    was APPROVED, HELD FOR VERIFICATION, or BLOCKED, along with the specific reasons,
    enabling the agent to reason over policy and spec violations.
    
    Security Contract:
        Strictly FAIL-CLOSED. If SpendGuard is unreachable or times out, the tool returns
        a BLOCKED observation.
    """
    name: str = "spendguard_checkout"
    description: str = (
        "Submit a proposed purchase to the SpendGuard Corporate Trust Gateway for policy, "
        "spec verification, budget limit, and fraud checks. Always call this tool to finalize "
        "and pay for an item. The tool returns whether the purchase is APPROVED, HELD FOR VERIFICATION, "
        "or BLOCKED with detailed reasons."
    )
    args_schema: Type[BaseModel] = SpendGuardCheckoutInput
    client: Optional[SpendGuardClient] = None

    def __init__(self, client: Optional[SpendGuardClient] = None, **kwargs):
        super().__init__(**kwargs)
        self.client = client or SpendGuardClient()

    def _run(
        self,
        sku: str,
        amount: float,
        merchant: str,
        category: str = "electronics",
        brand: Optional[str] = None,
        model: Optional[str] = None,
        claimed_specs: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = "",
        agent_id: Optional[str] = None,
        mandate_id: Optional[str] = "mandate_shop_enterprise",
        user_intent_id: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Executes the checkout check through SpendGuardClient."""
        tx_id = f"tx_langchain_{uuid.uuid4().hex[:8]}"
        resolved_agent_id = agent_id or f"lc_agent_{uuid.uuid4().hex[:6]}"
        intent_id = user_intent_id or f"intent_lc_{tx_id}"

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
            assert self.client is not None
            receipt = self.client.evaluate(tx)
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

        # Format natural language observation for LLM agent reasoning
        if receipt.is_allowed:
            order_info = f" Razorpay Order ID: {receipt.razorpay_order_id}." if receipt.razorpay_order_id else ""
            return (
                f"APPROVED: Purchase of {sku} for ₹{amount:,.2f} at {merchant} authorized by SpendGuard Trust Gateway."
                f"{order_info} All 4 trust pillars passed. You may inform the user the purchase succeeded."
            )
        elif receipt.is_verification_required:
            hold_info = f" (Hold ID: {receipt.payment_hold_id})" if receipt.payment_hold_id else ""
            return (
                f"HELD FOR VERIFICATION: Purchase of {sku} requires human operator approval.{hold_info} "
                f"Reason: {receipt.decision_reason}. Inform the user that the order is pending compliance review."
            )
        else:  # is_blocked
            return (
                f"BLOCKED: Purchase of {sku} was rejected by SpendGuard Trust Gateway. "
                f"Reason: {receipt.decision_reason}. "
                "You must select a compliant alternative product that satisfies corporate policies or abort."
            )

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        """Asynchronous execution (delegates to synchronous run)."""
        return self._run(*args, **kwargs)
