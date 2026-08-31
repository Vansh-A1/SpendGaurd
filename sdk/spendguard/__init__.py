"""
SpendGuard Python SDK
Framework-agnostic trust gate and transaction verification client for AI agents.
"""

from .client import SpendGuardClient
from .models import (
    TransactionRequest,
    DecisionReceipt,
    ClaimedProduct,
    AuthorizationResultModel,
    IntentFidelityResultModel,
    BehavioralRiskResultModel,
    EvidenceResultModel,
    GoalDriftResultModel,
)
from .exceptions import (
    SpendGuardError,
    SpendGuardConnectionError,
    SpendGuardAPIError,
    PurchaseBlocked,
    VerificationRequired,
)
from .integrations.langchain import SpendGuardCheckoutTool
from .integrations.mcp_server import create_mcp_server
from .integrations.native_schemas import (
    OPENAI_TOOL_SCHEMA,
    ANTHROPIC_TOOL_SCHEMA,
    get_openai_tool_schema,
    get_anthropic_tool_schema,
    execute_native_checkout,
)

__version__ = "0.1.0"

__all__ = [
    "SpendGuardClient",
    "SpendGuardCheckoutTool",
    "create_mcp_server",
    "OPENAI_TOOL_SCHEMA",
    "ANTHROPIC_TOOL_SCHEMA",
    "get_openai_tool_schema",
    "get_anthropic_tool_schema",
    "execute_native_checkout",
    "TransactionRequest",
    "DecisionReceipt",
    "ClaimedProduct",
    "AuthorizationResultModel",
    "IntentFidelityResultModel",
    "BehavioralRiskResultModel",
    "EvidenceResultModel",
    "GoalDriftResultModel",
    "SpendGuardError",
    "SpendGuardConnectionError",
    "SpendGuardAPIError",
    "PurchaseBlocked",
    "VerificationRequired",
]
