"""
SpendGuard Python SDK - 5-Line Quickstart Example
Shows import -> client init -> evaluate() -> verdict check
"""

from spendguard import SpendGuardClient, TransactionRequest

# 1. Initialize client
client = SpendGuardClient(base_url="http://localhost:8000")

# 2. Formulate proposed purchase
transaction = TransactionRequest(
    id="tx_quickstart_01",
    agent_id="sim_shopping_agent_01",
    mandate_id="mandate_shop_enterprise",
    user_intent_id="intent_dev_01",
    claimed_product={"brand": "Dell", "model": "G15 5530", "price": 89990.0},
    actual_sku="ELEC-DELL-G15-4060",
    amount=89990.0,
    category="electronics",
    merchant="Dell Official Store",
)

# 3. Evaluate across 4 Trust Pillars
receipt = client.evaluate(transaction)

# 4. Check verdict
if receipt.is_blocked:
    print(f"🛑 Purchase Blocked: {receipt.decision_reason}")
elif receipt.is_verification_required:
    print(f"⚠️ Held for Human Review: {receipt.decision_reason}")
else:
    print(f"✅ Purchase Approved! Razorpay Order: {receipt.razorpay_order_id}")
