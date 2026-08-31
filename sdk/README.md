# SpendGuard Python SDK

Framework-agnostic trust gate and transaction verification client for AI agents.

## Quickstart (5 lines)

```python
from spendguard import SpendGuardClient, TransactionRequest

client = SpendGuardClient(base_url="http://localhost:8000")
receipt = client.evaluate(transaction)
if receipt.is_blocked:
    raise RuntimeError(f"SpendGuard blocked purchase: {receipt.decision_reason}")
```

## Installation

```bash
pip install -e .
```

## Usage Example

```python
from spendguard import SpendGuardClient, TransactionRequest

client = SpendGuardClient(base_url="http://localhost:8000")

# Propose an agent purchase
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

receipt = client.evaluate(tx)

print("Decision:", receipt.decision)              # ALLOW | VERIFY | BLOCK
print("Reason:", receipt.decision_reason)
print("Pillars:", {
    "authority": receipt.authorization,
    "intent": receipt.intent_fidelity,
    "evidence": receipt.evidence,
    "behavior": receipt.behavioral_risk,
})
```
