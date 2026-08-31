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
    SpendGuardAPIError,
    PurchaseBlocked,
    VerificationRequired,
)

__version__ = "1.0.0"

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
    "SpendGuardAPIError",
    "PurchaseBlocked",
    "VerificationRequired",
]
