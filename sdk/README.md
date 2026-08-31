# SpendGuard Python SDK (v0.1.0)

Framework-agnostic trust gate and transaction verification client for AI agents.

## Security Contract: Fail-Closed
If the SpendGuard gateway is unreachable, times out, or returns a transport failure, `SpendGuardClient` raises `SpendGuardConnectionError`. It **never** defaults to an ALLOW verdict or allows unverified agent purchases to proceed.

## Installation

```bash
pip install -e .
```

## Quickstart (5 lines)

```python
from spendguard import SpendGuardClient, TransactionRequest

client = SpendGuardClient(base_url="http://localhost:8000", api_key="sk_live_...")
receipt = client.evaluate(transaction)
if receipt.is_blocked:
    print(f"SpendGuard blocked purchase: {receipt.decision_reason}")
```

## Configuration & Usage

### 1. Default Evaluation (No Exceptions Raised)
By default, `.evaluate()` returns a typed `DecisionReceipt` model allowing your agent stack to inspect results:

```python
from spendguard import SpendGuardClient, TransactionRequest

# Initialize client (api_key is required for remote/staging/prod environments)
client = SpendGuardClient(
    base_url="https://spendguard.internal.net",
    api_key="sg_live_secret_key_here",
    timeout=10.0, # configurable network timeout (default: 10s)
)

tx = TransactionRequest(
    id="tx_dev_001",
    agent_id="shopping_agent_01",
    mandate_id="mandate_shop_enterprise",
    user_intent_id="intent_dev_001",
    claimed_product={
        "sku": "ELEC-DELL-G15-4060",
        "brand": "Dell",
        "model": "G15 5530 Gaming Laptop",
        "specs": {"ram_gb": 16, "gpu": "RTX 4060", "cpu": "Intel i7-13650HX"}
    },
    actual_sku="ELEC-DELL-G15-4060",
    amount=89990.0,
    category="electronics",
    merchant="Dell Official Store",
)

# Evaluates across all 4 Trust Pillars (Authority, Intent Fidelity, Evidence, Behavioral Risk)
receipt = client.evaluate(tx)

if receipt.is_allowed:
    print("✅ Approved! Order ID:", receipt.razorpay_order_id)
elif receipt.is_verification_required:
    print("⚠️ Held for Operator Review:", receipt.decision_reason)
elif receipt.is_blocked:
    print("🛑 Blocked:", receipt.decision_reason)
```

### 2. Opt-in Exception Handling
For agent frameworks that prefer exceptions to interrupt execution loops:

```python
from spendguard import SpendGuardClient, PurchaseBlocked, VerificationRequired

try:
    receipt = client.evaluate(tx, raise_on_block=True, raise_on_verify=True)
except PurchaseBlocked as err:
    print(f"Action Aborted: {err.reason}")
except VerificationRequired as err:
    print(f"Action Paused for Human Approval: {err.reason}")
```
