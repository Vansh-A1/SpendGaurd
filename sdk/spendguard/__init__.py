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

__version__ = "0.1.0"

__all__ = [
    "SpendGuardClient",
    "SpendGuardCheckoutTool",
    "create_mcp_server",
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
