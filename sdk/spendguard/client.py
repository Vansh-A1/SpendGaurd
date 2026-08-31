import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone

from .models import TransactionRequest, DecisionReceipt, ClaimedProduct
from .exceptions import SpendGuardError, SpendGuardAPIError, PurchaseBlocked, VerificationRequired


class SpendGuardClient:
    """
    SpendGuard Framework-Agnostic Python SDK Client.
    Provides synchronous client access to the SpendGuard AI Trust Gate API.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """
        Initializes the SpendGuard Client.
        
        Args:
            base_url: The root URL of the SpendGuard API gateway (default: http://localhost:8000).
            api_key: Optional API key for header authentication.
            token: Optional JWT bearer token for console/API authentication.
            timeout: HTTP request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SpendGuard-Python-SDK/1.0.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _json_serial(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def evaluate(
        self,
        transaction: Union[TransactionRequest, Dict[str, Any]],
        raise_on_block: bool = False,
        raise_on_verify: bool = False,
    ) -> DecisionReceipt:
        """
        Evaluates a proposed agent transaction through SpendGuard's 4-Pillar Trust Gate.
        
        Args:
            transaction: TransactionRequest instance or raw dictionary representing the transaction.
            raise_on_block: If True, raises PurchaseBlocked exception if decision is BLOCK.
            raise_on_verify: If True, raises VerificationRequired exception if decision is VERIFY.
            
        Returns:
            DecisionReceipt: Complete decision receipt with verdict, reason, pillar signals, and provenance trail.
        """
        if isinstance(transaction, dict):
            tx_obj = TransactionRequest(**transaction)
        elif isinstance(transaction, TransactionRequest):
            tx_obj = transaction
        else:
            raise TypeError(f"Expected TransactionRequest or dict, got {type(transaction)}")

        url = f"{self.base_url}/transactions/evaluate"
        payload_bytes = json.dumps(tx_obj.model_dump(), default=self._json_serial).encode("utf-8")
        headers = self._get_headers()

        req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                raw_body = resp.read().decode("utf-8")
                data = json.loads(raw_body)
                receipt = DecisionReceipt(**data)
        except urllib.error.HTTPError as err:
            err_body = None
            try:
                err_body = err.read().decode("utf-8")
                parsed = json.loads(err_body)
                err_detail = parsed.get("detail", err_body)
            except Exception:
                err_detail = str(err)
            raise SpendGuardAPIError(
                message=f"SpendGuard API error (HTTP {err.code}): {err_detail}",
                status_code=err.code,
                response_body=err_body,
            ) from err
        except urllib.error.URLError as err:
            raise SpendGuardAPIError(
                message=f"Failed to connect to SpendGuard API at {self.base_url}: {err.reason}",
            ) from err
        except Exception as err:
            raise SpendGuardError(f"Unexpected SpendGuard SDK error: {err}") from err

        if raise_on_block and receipt.is_blocked:
            raise PurchaseBlocked(receipt.decision_reason, receipt=receipt)

        if raise_on_verify and receipt.is_verification_required:
            raise VerificationRequired(receipt.decision_reason, receipt=receipt)

        return receipt

    def get_receipt(self, transaction_id: str) -> DecisionReceipt:
        """
        Fetches an existing DecisionReceipt from the SpendGuard gateway by transaction ID.
        """
        url = f"{self.base_url}/transactions/{transaction_id}/receipt"
        headers = self._get_headers()
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return DecisionReceipt(**data)
        except urllib.error.HTTPError as err:
            raise SpendGuardAPIError(
                message=f"Receipt {transaction_id} not found or error (HTTP {err.code})",
                status_code=err.code,
            ) from err
        except Exception as err:
            raise SpendGuardError(f"Failed to retrieve receipt: {err}") from err

    def health(self) -> Dict[str, Any]:
        """Checks health status of the SpendGuard gateway API."""
        url = f"{self.base_url}/health"
        headers = self._get_headers()
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
