from typing import Optional, Any


class SpendGuardError(Exception):
    """Base exception for all SpendGuard SDK operations."""
    pass


class SpendGuardConnectionError(SpendGuardError):
    """
    Raised when SpendGuard gateway is unreachable, connection is refused, or times out.
    Enforces FAIL-CLOSED behavior: unverified agent transactions are never allowed to proceed silently.
    """
    def __init__(self, message: str, endpoint: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(message)
        self.endpoint = endpoint
        self.timeout = timeout


class SpendGuardAPIError(SpendGuardError):
    """Raised when the SpendGuard API returns an HTTP 4xx or 5xx error response."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class PurchaseBlocked(SpendGuardError):
    """Raised when a proposed transaction is evaluated as BLOCK by SpendGuard's trust gates (opt-in)."""
    def __init__(self, reason: str, receipt: Optional[Any] = None):
        super().__init__(f"Purchase blocked by SpendGuard: {reason}")
        self.reason = reason
        self.receipt = receipt


class VerificationRequired(SpendGuardError):
    """Raised when a proposed transaction is placed on hold for human verification (VERIFY) (opt-in)."""
    def __init__(self, reason: str, receipt: Optional[Any] = None):
        super().__init__(f"Purchase held for verification by SpendGuard: {reason}")
        self.reason = reason
        self.receipt = receipt
