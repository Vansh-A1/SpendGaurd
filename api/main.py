import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
import pandas as pd
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query, status

from data.schema import TransactionRequest, Product
from policy.schema import Mandate
from intent.schema import UserIntent
from data.catalog import get_catalog
from decision.engine import evaluate_transaction, DecisionReceipt
from api.db import (
    init_db,
    save_transaction_evaluation,
    get_transactions,
    get_transaction_receipt,
    update_transaction_decision,
    get_audit_logs,
)

# Lazy-loaded cache
REPO_ROOT = Path(__file__).resolve().parent.parent
MANDATES_CACHE: Dict[str, Mandate] = {}
INTENTS_CACHE: Dict[str, UserIntent] = {}
CATALOG_CACHE: List[Product] = []
RISK_MODEL_CACHE: Any = None


def get_resources():
    global MANDATES_CACHE, INTENTS_CACHE, CATALOG_CACHE, RISK_MODEL_CACHE
    if not MANDATES_CACHE:
        mandates_file = REPO_ROOT / "data" / "mandates.json"
        if mandates_file.exists():
            with open(mandates_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                MANDATES_CACHE = {m["id"]: Mandate(**m) for m in data}

    if not INTENTS_CACHE:
        intents_file = REPO_ROOT / "data" / "intents.json"
        if intents_file.exists():
            with open(intents_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                INTENTS_CACHE = {k: UserIntent(**v) for k, v in data.items()}

    if not CATALOG_CACHE:
        CATALOG_CACHE = get_catalog()

    if RISK_MODEL_CACHE is None:
        model_file = REPO_ROOT / "model" / "risk_model.pkl"
        if model_file.exists():
            with open(model_file, "rb") as f:
                RISK_MODEL_CACHE = pickle.load(f)

    return MANDATES_CACHE, INTENTS_CACHE, CATALOG_CACHE, RISK_MODEL_CACHE


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    get_resources()
    yield

app = FastAPI(title="SpendGuard Trust Layer API", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


class VerifyRequest(BaseModel):
    approved: bool


@app.post("/transactions/evaluate", response_model=DecisionReceipt)
def evaluate(transaction: TransactionRequest):
    """
    Evaluates an agent purchase request across the 4 Trust Gate pillars,
    persists the DecisionReceipt and provenance trail to SQLite, and logs an audit event.
    """
    mandates_map, intents_map, catalog, risk_model = get_resources()

    # 1. Resolve Mandate
    mandate = mandates_map.get(transaction.mandate_id)
    if not mandate:
        # Fallback to agent default mandate if found
        mandate = next((m for m in mandates_map.values() if m.agent_id == transaction.agent_id), None)
        if not mandate:
            raise HTTPException(status_code=404, detail=f"Mandate {transaction.mandate_id} not found")

    # 2. Resolve UserIntent
    intent = intents_map.get(transaction.user_intent_id)
    if not intent:
        # Default intent if not found in cache
        intent = UserIntent(
            id=transaction.user_intent_id or f"intent_{transaction.id}",
            agent_id=transaction.agent_id,
            hard_requirements={"brand": transaction.claimed_product.get("brand", "")},
            soft_preferences={},
            substitution_allowed=False,
            created_at=transaction.timestamp,
        )

    # 3. Build history dataframe from DB for chronological feature velocity
    prior_txs = get_transactions(agent_id=transaction.agent_id)
    if prior_txs:
        history_df = pd.DataFrame(prior_txs)
    else:
        history_df = None

    # 4. Evaluate through Decision Engine
    receipt = evaluate_transaction(
        transaction=transaction,
        mandate=mandate,
        intent=intent,
        catalog=catalog,
        risk_model=risk_model,
        history_df=history_df,
    )

    # 5. Persist to DB
    tx_dict = transaction.model_dump(mode="json")
    receipt_dict = receipt.model_dump(mode="json")
    save_transaction_evaluation(tx_dict, receipt_dict, actor="system")

    return receipt


@app.get("/transactions")
def list_transactions(
    decision: Optional[Literal["ALLOW", "VERIFY", "BLOCK"]] = None,
    agent_id: Optional[str] = None,
):
    """Returns a list of evaluated transactions with optional filters, newest first."""
    return get_transactions(decision=decision, agent_id=agent_id)


@app.get("/transactions/{id}/receipt")
def get_receipt(id: str):
    """Returns the complete DecisionReceipt for a single transaction with joined provenance trail."""
    receipt = get_transaction_receipt(id)
    if not receipt:
        raise HTTPException(status_code=404, detail=f"Transaction {id} not found")
    return receipt


@app.post("/transactions/{id}/verify")
def verify_transaction(id: str, body: VerifyRequest):
    """
    Human-in-the-loop review endpoint for transactions in VERIFY state.
    Updates decision to ALLOW or BLOCK and logs an audit record.
    """
    receipt = get_transaction_receipt(id)
    if not receipt:
        raise HTTPException(status_code=404, detail=f"Transaction {id} not found")

    if receipt["decision"] != "VERIFY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Transaction {id} is in '{receipt['decision']}' state, not 'VERIFY'",
        )

    new_decision = "ALLOW" if body.approved else "BLOCK"
    action = "approved" if body.approved else "denied"
    reason = (
        "human approved after verification review"
        if body.approved
        else "human denied after verification review"
    )

    success = update_transaction_decision(
        transaction_id=id,
        new_decision=new_decision,
        actor="human",
        action=action,
        reason=reason,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update transaction decision")

    updated_receipt = get_transaction_receipt(id)
    return updated_receipt
