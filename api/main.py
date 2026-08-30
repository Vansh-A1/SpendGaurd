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
    get_trust_snapshot,
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

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SpendGuard Trust Layer API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


class VerifyRequest(BaseModel):
    approved: bool


from payments.razorpay_client import (
    create_test_order,
    create_payment_hold,
    capture_payment_hold,
    void_payment_hold,
)
from api.escalations import (
    create_escalation,
    get_pending_escalations,
    resolve_escalation,
    process_escalation_timeouts,
    dispatch_escalation_webhook,
    register_webhook,
    get_webhook_url,
)
from session.manager import (
    list_sessions,
    get_session,
    get_session_transactions,
)
from api.db import get_db_connection


class WebhookConfigRequest(BaseModel):
    url: str


@app.post("/transactions/evaluate", response_model=DecisionReceipt)
def evaluate(transaction: TransactionRequest):
    """
    Evaluates an agent purchase request across the 4 Trust Gate pillars,
    triggers real Razorpay test-mode orders on ALLOW decisions,
    places funds on authorization hold and registers escalations on VERIFY decisions,
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

    # 5. Two-Phase Payment Execution
    if receipt.decision == "ALLOW":
        try:
            order = create_test_order(
                amount=transaction.amount,
                currency="INR",
                receipt_id=transaction.id,
            )
            receipt.razorpay_order_id = order.get("id")
        except Exception as e:
            receipt.payment_error = str(e)
    elif receipt.decision == "VERIFY":
        try:
            hold = create_payment_hold(
                amount=transaction.amount,
                currency="INR",
                transaction_id=transaction.id,
            )
            receipt.payment_hold_id = hold.get("hold_id")
            receipt.payment_hold_status = hold.get("status")

            # Register in escalation queue
            create_escalation(
                transaction_id=transaction.id,
                agent_id=transaction.agent_id,
                amount=transaction.amount,
                payment_hold_id=hold.get("hold_id"),
            )

            # Dispatch non-blocking webhook
            dispatch_escalation_webhook(
                transaction.model_dump(mode="json"),
                receipt.model_dump(mode="json"),
            )
        except Exception as e:
            receipt.payment_error = str(e)

    # 6. Persist to DB
    tx_dict = transaction.model_dump(mode="json")
    receipt_dict = receipt.model_dump(mode="json")
    save_transaction_evaluation(tx_dict, receipt_dict, actor="system")

    return receipt


@app.get("/transactions")
def list_transactions(
    decision: Optional[Literal["ALLOW", "VERIFY", "BLOCK"]] = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
):
    """Returns a list of evaluated transactions with optional filters, newest first."""
    return get_transactions(decision=decision, agent_id=agent_id, session_id=session_id)


@app.get("/transactions/{id}/receipt")
def get_receipt(id: str):
    """Returns the complete DecisionReceipt for a single transaction with joined provenance trail."""
    receipt = get_transaction_receipt(id)
    if not receipt:
        raise HTTPException(status_code=404, detail=f"Transaction {id} not found")
    return receipt


@app.get("/transactions/{id}/snapshot")
def get_snapshot(id: str):
    """Returns the exported TrustSnapshot audit artifact for a single transaction."""
    snapshot = get_trust_snapshot(id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Trust snapshot for transaction {id} not found")
    return snapshot


@app.post("/transactions/{id}/verify")
def verify_transaction(id: str, body: VerifyRequest):
    """
    Human-in-the-loop review endpoint for transactions in VERIFY state.
    Updates decision to ALLOW or BLOCK, captures or voids two-phase payment hold, and logs audit record.
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

    razorpay_order_id = None
    payment_error = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT amount, payment_hold_id FROM transactions WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()

    amt = float(row["amount"]) if row else 0.0
    hold_id = row["payment_hold_id"] if row and "payment_hold_id" in row.keys() else receipt.get("payment_hold_id")

    # 1. Capture hold on approval
    if body.approved:
        try:
            order = create_test_order(
                amount=amt,
                currency="INR",
                receipt_id=id,
            )
            razorpay_order_id = order.get("id")
            if hold_id:
                capture_payment_hold(hold_id=hold_id, amount=amt, transaction_id=id)
        except Exception as e:
            payment_error = str(e)
        resolve_escalation(id, action="approved")
    else:
        # 2. Void hold on denial
        if hold_id:
            try:
                void_payment_hold(hold_id=hold_id, reason="human_denied")
            except Exception as e:
                payment_error = str(e)
        resolve_escalation(id, action="denied")

    success = update_transaction_decision(
        transaction_id=id,
        new_decision=new_decision,
        actor="human",
        action=action,
        reason=reason,
        razorpay_order_id=razorpay_order_id,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update transaction decision")

    updated_receipt = get_transaction_receipt(id)
    if payment_error:
        updated_receipt["payment_error"] = payment_error
    return updated_receipt


# -----------------------------------------------------------------------------
# Sessions Endpoints
# -----------------------------------------------------------------------------
@app.get("/sessions")
def list_all_sessions(agent_id: Optional[str] = None):
    """Lists all registered PurchaseSessions and their associated transaction history."""
    sessions = list_sessions(agent_id=agent_id)
    result = []
    for s in sessions:
        tx_rows = get_transactions(session_id=s.session_id)
        s_dict = s.model_dump(mode="json")
        s_dict["transactions"] = tx_rows
        s_dict["transaction_count"] = len(tx_rows)
        s_dict["total_spent"] = sum(
            float(t["amount"]) for t in tx_rows if t.get("decision") in ("ALLOW", "VERIFY")
        )
        result.append(s_dict)
    return result


@app.get("/sessions/{session_id}")
def get_session_details(session_id: str):
    """Returns detailed session metadata, declared budget/items, and transaction logs."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"PurchaseSession {session_id} not found")

    tx_rows = get_transactions(session_id=session_id)
    s_dict = session.model_dump(mode="json")
    s_dict["transactions"] = tx_rows
    s_dict["transaction_count"] = len(tx_rows)
    s_dict["total_spent"] = sum(
        float(t["amount"]) for t in tx_rows if t.get("decision") in ("ALLOW", "VERIFY")
    )
    return s_dict


# -----------------------------------------------------------------------------
# Escalations & SLA Management Endpoints
# -----------------------------------------------------------------------------
@app.get("/escalations")
def list_escalations():
    """Lists all active pending VERIFY items in the human review queue with remaining SLA time."""
    return get_pending_escalations()


@app.post("/escalations/process_timeouts")
def trigger_timeout_processing():
    """Scans and automatically denies escalations that have exceeded their SLA timeout."""
    timed_out = process_escalation_timeouts()
    return {"status": "ok", "timed_out_count": len(timed_out), "items": timed_out}


@app.post("/admin/webhook")
def set_webhook(body: WebhookConfigRequest):
    """Registers a webhook URL for real-time escalation notifications."""
    register_webhook(body.url)
    return {"status": "ok", "webhook_url": body.url}


@app.get("/admin/webhook")
def get_current_webhook():
    """Retrieves the active escalation webhook configuration."""
    return {"webhook_url": get_webhook_url()}


from fastapi.responses import FileResponse
import csv

@app.get("/")
def serve_dashboard():
    frontend_path = REPO_ROOT / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(str(frontend_path))
    return {"message": "SpendGuard API is running. Access /docs for Swagger UI."}


@app.post("/admin/seed_scenarios")
def seed_scenarios():
    """Batch-evaluates and persists all scenarios from data/scenarios.csv."""
    scenarios_csv = REPO_ROOT / "data" / "scenarios.csv"
    if not scenarios_csv.exists():
        raise HTTPException(status_code=404, detail="scenarios.csv not found")

    rows = []
    with open(scenarios_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            r["claimed_product"] = json.loads(r["claimed_product"])
            r["amount"] = float(r["amount"])
            tx = TransactionRequest(**r)
            evaluate(tx)
            rows.append(tx)

    return {"status": "ok", "count": len(rows)}
