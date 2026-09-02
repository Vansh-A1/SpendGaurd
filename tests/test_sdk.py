"""
Tests for SpendGuard Python SDK (Framework-Agnostic Client).
Validates models, client initialization, default evaluation behavior, fail-closed connection handling,
opt-in exceptions, and end-to-end API round-trips.
"""

import json
import uuid
import socket
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

import spendguard
from spendguard import (
    SpendGuardClient,
    TransactionRequest,
    DecisionReceipt,
    ClaimedProduct,
    PurchaseBlocked,
    VerificationRequired,
    SpendGuardAPIError,
    SpendGuardConnectionError,
)
from api.main import app


@pytest.fixture
def api_client():
    return TestClient(app)


def test_sdk_package_exports_and_version():
    """Confirms version 0.1.0 and all key classes/exceptions are exported."""
    assert spendguard.__version__ == "0.1.0"
    assert SpendGuardClient is not None
    assert TransactionRequest is not None
    assert DecisionReceipt is not None
    assert SpendGuardConnectionError is not None
    assert PurchaseBlocked is not None
    assert VerificationRequired is not None


def test_sdk_model_serialization_and_properties():
    """Validates Pydantic serialization and helper properties on DecisionReceipt."""
    tx = TransactionRequest(
        id="tx_sdk_test_01",
        agent_id="agent_01",
        mandate_id="mandate_shop_enterprise",
        user_intent_id="intent_01",
        claimed_product=ClaimedProduct(
            sku="ELEC-DELL-G15-4060",
            brand="Dell",
            model="G15 5530",
            specs={"ram_gb": 16, "gpu": "RTX 4060"},
        ),
        actual_sku="ELEC-DELL-G15-4060",
        amount=89990.0,
        category="electronics",
        merchant="Dell Official Store",
    )

    dumped = tx.model_dump()
    assert dumped["id"] == "tx_sdk_test_01"
    assert dumped["amount"] == 89990.0
    assert isinstance(dumped["claimed_product"], dict)

    receipt = DecisionReceipt(
        transaction_id="tx_sdk_test_01",
        decision="ALLOW",
        decision_reason="All checks passed",
    )
    assert receipt.is_allowed is True
    assert receipt.is_blocked is False
    assert receipt.is_verification_required is False

    block_receipt = DecisionReceipt(
        transaction_id="tx_sdk_test_02",
        decision="BLOCK",
        decision_reason="budget_exceeded",
    )
    assert block_receipt.is_blocked is True
    assert block_receipt.is_allowed is False


def test_sdk_default_evaluation_returns_receipt_without_raising():
    """
    Validates the default (no-flag) behavior of .evaluate():
    When evaluate() is called with no flags, it returns the DecisionReceipt directly
    for both ALLOW and BLOCK transactions without raising exceptions.
    """
    client = SpendGuardClient(base_url="http://localhost:8000", api_key="test_key_123")

    mock_block_data = {
        "transaction_id": "tx_default_block_01",
        "decision": "BLOCK",
        "decision_reason": "blocked: authorization failed (budget_exceeded)",
        "provenance_trail": [],
    }

    mock_http_response = MagicMock()
    mock_http_response.getcode.return_value = 200
    mock_http_response.read.return_value = json.dumps(mock_block_data).encode("utf-8")
    mock_http_response.__enter__.return_value = mock_http_response

    with patch("urllib.request.urlopen", return_value=mock_http_response) as mock_urlopen:
        tx = {
            "id": "tx_default_block_01",
            "agent_id": "agent_01",
            "mandate_id": "mandate_shop_enterprise",
            "user_intent_id": "intent_01",
            "claimed_product": {"brand": "Dell"},
            "actual_sku": "ELEC-DELL-G15-4060",
            "amount": 250000.0,
            "category": "electronics",
            "merchant": "Dell Official Store",
        }

        # Must NOT raise by default
        receipt = client.evaluate(tx)
        assert isinstance(receipt, DecisionReceipt)
        assert receipt.is_blocked is True
        assert receipt.decision == "BLOCK"
        assert "budget_exceeded" in receipt.decision_reason

        # Verify auth headers sent
        req_sent = mock_urlopen.call_args[0][0]
        assert req_sent.headers.get("X-api-key") == "test_key_123" or req_sent.headers.get("Authorization") == "Bearer test_key_123"


def test_sdk_fail_closed_on_unreachable_gateway():
    """
    CRITICAL SECURITY CONTRACT: FAIL-CLOSED.
    If SpendGuard API is unreachable or connection is refused, SpendGuardClient MUST raise
    SpendGuardConnectionError rather than silently returning an ALLOW or default state.
    """
    client = SpendGuardClient(base_url="http://unreachable-spendguard-host:8000", timeout=5.0)

    from urllib.error import URLError

    with patch("urllib.request.urlopen", side_effect=URLError(ConnectionRefusedError("Connection refused"))):
        with pytest.raises(SpendGuardConnectionError) as exc_info:
            client.evaluate({
                "id": "tx_fail_closed_01",
                "agent_id": "agent_01",
                "mandate_id": "mandate_shop_enterprise",
                "user_intent_id": "intent_01",
                "claimed_product": {"brand": "Dell"},
                "actual_sku": "ELEC-DELL-G15-4060",
                "amount": 50000.0,
                "category": "electronics",
                "merchant": "Dell Official Store",
            })
        assert "Fail-Closed" in str(exc_info.value)
        assert "Failed to connect to SpendGuard" in str(exc_info.value)


def test_sdk_fail_closed_on_network_timeout():
    """
    CRITICAL SECURITY CONTRACT: FAIL-CLOSED ON TIMEOUT.
    If the trust gate evaluation times out, client MUST raise SpendGuardConnectionError.
    """
    client = SpendGuardClient(base_url="http://localhost:8000", timeout=2.0)

    with patch("urllib.request.urlopen", side_effect=socket.timeout("Socket timed out")):
        with pytest.raises(SpendGuardConnectionError) as exc_info:
            client.evaluate({
                "id": "tx_timeout_01",
                "agent_id": "agent_01",
                "mandate_id": "mandate_shop_enterprise",
                "user_intent_id": "intent_01",
                "claimed_product": {"brand": "Dell"},
                "actual_sku": "ELEC-DELL-G15-4060",
                "amount": 50000.0,
                "category": "electronics",
                "merchant": "Dell Official Store",
            })
        assert "timed out" in str(exc_info.value).lower()
        assert "Fail-Closed" in str(exc_info.value)


def test_sdk_evaluate_raise_on_block_exception():
    """Verifies that opt-in raise_on_block=True correctly raises PurchaseBlocked."""
    client = SpendGuardClient()

    mock_resp_data = {
        "transaction_id": "tx_block_01",
        "decision": "BLOCK",
        "decision_reason": "blocked: authorization failed (category_not_allowed)",
        "provenance_trail": [],
    }

    mock_http_response = MagicMock()
    mock_http_response.getcode.return_value = 200
    mock_http_response.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_http_response.__enter__.return_value = mock_http_response

    with patch("urllib.request.urlopen", return_value=mock_http_response):
        with pytest.raises(PurchaseBlocked) as exc_info:
            client.evaluate(
                {
                    "id": "tx_block_01",
                    "agent_id": "agent_01",
                    "mandate_id": "mandate_shop_enterprise",
                    "user_intent_id": "intent_01",
                    "claimed_product": {"brand": "DeLonghi"},
                    "actual_sku": "ELEC-COFFEE-01",
                    "amount": 15000.0,
                    "category": "appliances",
                    "merchant": "Amazon",
                },
                raise_on_block=True,
            )
        assert "category_not_allowed" in str(exc_info.value)
        assert exc_info.value.receipt.is_blocked is True


def test_sdk_evaluate_raise_on_verify_exception():
    """Verifies that opt-in raise_on_verify=True correctly raises VerificationRequired."""
    client = SpendGuardClient()

    mock_resp_data = {
        "transaction_id": "tx_verify_01",
        "decision": "VERIFY",
        "decision_reason": "held for verification: soft preferences mismatch (color)",
        "provenance_trail": [],
    }

    mock_http_response = MagicMock()
    mock_http_response.getcode.return_value = 200
    mock_http_response.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_http_response.__enter__.return_value = mock_http_response

    with patch("urllib.request.urlopen", return_value=mock_http_response):
        with pytest.raises(VerificationRequired) as exc_info:
            client.evaluate(
                {
                    "id": "tx_verify_01",
                    "agent_id": "agent_01",
                    "mandate_id": "mandate_shop_enterprise",
                    "user_intent_id": "intent_01",
                    "claimed_product": {"brand": "Sony"},
                    "actual_sku": "ELEC-SONY-WH1000XM5-BLK",
                    "amount": 29990.0,
                    "category": "electronics",
                    "merchant": "Sony Center",
                },
                raise_on_verify=True,
            )
        assert "held for verification" in str(exc_info.value)


def test_sdk_api_error_handling():
    """Verifies that HTTP 4xx/5xx errors are cleanly wrapped in SpendGuardAPIError."""
    client = SpendGuardClient(base_url="http://localhost:8000")

    from urllib.error import HTTPError
    from io import BytesIO

    http_err = HTTPError(
        url="http://localhost:8000/transactions/evaluate",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=BytesIO(b'{"detail": "Mandate mandate_999 not found"}'),
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(SpendGuardAPIError) as exc_info:
            client.evaluate({
                "id": "tx_err_01",
                "agent_id": "agent_01",
                "mandate_id": "mandate_999",
                "user_intent_id": "intent_01",
                "claimed_product": {},
                "actual_sku": "SKU-01",
                "amount": 100.0,
                "category": "electronics",
                "merchant": "Amazon",
            })
        assert exc_info.value.status_code == 404
        assert "mandate_999 not found" in str(exc_info.value)


def test_sdk_roundtrip_against_fastapi_app(api_client):
    """End-to-end integration test validating that SDK payload matches FastAPI schema exactly."""
    tx = TransactionRequest(
        id=f"tx_sdk_e2e_clean_sony_{uuid.uuid4().hex[:8]}",
        agent_id="sim_shopping_agent_01",
        mandate_id="mandate_shop_enterprise",
        user_intent_id="intent_sony_clean",
        claimed_product={
            "sku": "ELEC-SONY-WHCH720N-BLK",
            "brand": "Sony",
            "model": "WH-CH720N",
            "specs": {"anc": True, "battery_hours": 35, "color": "black", "form_factor": "over-ear"},
        },
        actual_sku="ELEC-SONY-WHCH720N-BLK",
        amount=9990.0,
        category="electronics",
        merchant="Sony Center",
        scenario_type="clean_baseline",
        expected_decision="ALLOW",
    )

    # Direct API call via FastAPI TestClient using SDK serialization
    payload = json.loads(json.dumps(tx.model_dump(), default=lambda o: o.isoformat() if hasattr(o, 'isoformat') else str(o)))
    res = api_client.post("/transactions/evaluate", json=payload)
    assert res.status_code == 200

    # Parse through SDK DecisionReceipt
    receipt = DecisionReceipt(**res.json())
    assert receipt.decision == "ALLOW"
    assert receipt.is_allowed is True
    assert "allowed" in receipt.decision_reason
