import json
import urllib.request
import urllib.error
import socket
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone

from .models import TransactionRequest, DecisionReceipt, ClaimedProduct
from .exceptions import (
    SpendGuardError,
    SpendGuardConnectionError,
    SpendGuardAPIError,
    PurchaseBlocked,
    VerificationRequired,
)


class SpendGuardClient:
    """
    SpendGuard Framework-Agnostic Python SDK Client.
    
    Provides synchronous evaluation of proposed agent transactions against SpendGuard's
    Four-Pillar Trust Gate (Authorization, Intent Fidelity, Behavioral Risk, and Evidence).
    
    Security Guarantee:
        Strictly FAIL-CLOSED. If the gateway is unreachable or request times out,
        the client raises SpendGuardConnectionError. It will NEVER silently return an
        ALLOW-like state or let unverified purchases through.
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
            api_key: Secret API Key for SpendGuard authentication. Optional for local development,
                     required for non-local / staging / production deployments.
            token: Optional JWT bearer token for console/API authentication.
            timeout: Network request timeout in seconds (default: 10.0s). If exceeded, raises SpendGuardConnectionError.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.token = token
        self.timeout = timeout

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SpendGuard-Python-SDK/0.1.0",
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        elif self.token:
            headers["Authorization"] = f"Bearer {self.token}"
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
        Evaluates a proposed agent transaction across SpendGuard's 4-Pillar Trust Gate.
        
        Default Behavior (No Flags):
            Returns the complete `DecisionReceipt` model without raising exceptions.
            The caller can inspect `receipt.decision`, `receipt.is_allowed`, `receipt.is_blocked`,
            `receipt.is_verification_required`, and `receipt.decision_reason`.
            
        Opt-In Exception Modes:
            - Set `raise_on_block=True` to immediately raise `PurchaseBlocked` if decision is BLOCK.
            - Set `raise_on_verify=True` to immediately raise `VerificationRequired` if decision is VERIFY.
            
        Fail-Closed Contract:
            If SpendGuard is unreachable, times out, or returns a transport error, this method
            raises `SpendGuardConnectionError`. It will NEVER default to an ALLOW verdict.
        
        Args:
            transaction: TransactionRequest model instance or raw dict of transaction attributes.
            raise_on_block: (Optional) If True, raises PurchaseBlocked when decision == BLOCK. Default: False.
            raise_on_verify: (Optional) If True, raises VerificationRequired when decision == VERIFY. Default: False.
            
        Returns:
            DecisionReceipt: Structured verdict containing decision, reason, pillar breakdowns, and provenance trail.
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
                raw_body = resp.read().decode("utf-8")
                data = json.loads(raw_body)
                receipt = DecisionReceipt(**data)
        except (socket.timeout, TimeoutError) as err:
            raise SpendGuardConnectionError(
                message=f"SpendGuard Trust Gate timed out after {self.timeout}s at {url} (Fail-Closed)",
                endpoint=url,
                timeout=self.timeout,
            ) from err
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
            # Handle socket timeout wrapped inside URLError
            if isinstance(err.reason, socket.timeout) or "timed out" in str(err.reason).lower():
                raise SpendGuardConnectionError(
                    message=f"SpendGuard Trust Gate timed out after {self.timeout}s at {url} (Fail-Closed)",
                    endpoint=url,
                    timeout=self.timeout,
                ) from err
            raise SpendGuardConnectionError(
                message=f"Failed to connect to SpendGuard gateway at {self.base_url}: {err.reason} (Fail-Closed)",
                endpoint=url,
                timeout=self.timeout,
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
        except (socket.timeout, TimeoutError) as err:
            raise SpendGuardConnectionError(
                message=f"SpendGuard receipt retrieval timed out after {self.timeout}s at {url}",
                endpoint=url,
                timeout=self.timeout,
            ) from err
        except urllib.error.HTTPError as err:
            raise SpendGuardAPIError(
                message=f"Receipt {transaction_id} not found or error (HTTP {err.code})",
                status_code=err.code,
            ) from err
        except urllib.error.URLError as err:
            raise SpendGuardConnectionError(
                message=f"Failed to connect to SpendGuard gateway at {self.base_url}: {err.reason}",
                endpoint=url,
            ) from err
        except Exception as err:
            raise SpendGuardError(f"Failed to retrieve receipt: {err}") from err

    def health(self) -> Dict[str, Any]:
        """Checks health status of the SpendGuard gateway API."""
        url = f"{self.base_url}/health"
        headers = self._get_headers()
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            raise SpendGuardConnectionError(
                message=f"SpendGuard gateway health check failed at {url}: {err}",
                endpoint=url,
            ) from err

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
