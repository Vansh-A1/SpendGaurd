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

__version__ = "0.1.0"

__all__ = [
    "SpendGuardClient",
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
