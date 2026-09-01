import json
import os
import pickle
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal
import bcrypt
import jwt
import pandas as pd
from pydantic import BaseModel
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse

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
        sim_file = REPO_ROOT / "simulator" / "trap_catalog.json"
        sim_items = []
        if sim_file.exists():
            with open(sim_file, "r", encoding="utf-8") as f:
                sim_data = json.load(f)
                sim_items = [
                    Product(
                        sku=p["sku"],
                        brand=p["brand"],
                        model=p["model"],
                        category=p["category"],
                        price=float(p["price"]),
                        specs=p.get("catalog_truth", {}),
                    )
                    for p in sim_data
                ]
        CATALOG_CACHE = get_catalog() + sim_items

    if RISK_MODEL_CACHE is None:
        model_file = REPO_ROOT / "model" / "risk_model.pkl"
        if model_file.exists():
            with open(model_file, "rb") as f:
                RISK_MODEL_CACHE = pickle.load(f)

    return MANDATES_CACHE, INTENTS_CACHE, CATALOG_CACHE, RISK_MODEL_CACHE


AUTH_DB_PATH = REPO_ROOT / "data" / "spendguard.db"
JWT_ALGORITHM = "HS256"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class LoginRequest(BaseModel):
    email: str
    password: str


def auth_connection():
    connection = sqlite3.connect(AUTH_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


JWT_SECRET = os.environ.get("JWT_SECRET", "spendguard-dev-secret-key-32-bytes-long")

import secrets

DEFAULT_USERS = [
    ("ADMIN", "admin", "SpendGuard Admin", "admin@spendguard.ai"),
    ("OPERATOR", "operator", "SpendGuard Operator", "operator@spendguard.ai"),
    ("VIEWER", "viewer", "SpendGuard Viewer", "viewer@spendguard.ai"),
]


def create_access_token(user: Dict[str, Any]) -> str:
    payload = {"sub": user["id"], "email": user["email"], "role": user["role"], "exp": datetime.now(timezone.utc) + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user: Dict[str, Any]) -> str:
    payload = {"sub": user["id"], "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": user["id"], "email": user["email"], "name": user.get("name", ""), "role": user["role"]}


def set_auth_cookies(response: Response, user: Dict[str, Any]) -> None:
    response.set_cookie("access_token", create_access_token(user), httponly=True, secure=False, samesite="lax", max_age=900, path="/")
    response.set_cookie("refresh_token", create_refresh_token(user), httponly=True, secure=False, samesite="lax", max_age=604800, path="/")


def find_user_by_email(email: str):
    with auth_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def find_user_by_id(user_id: str):
    with auth_connection() as connection:
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def authenticate_request(request: Request):
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        user = find_user_by_id(payload["sub"])
        return public_user(user) if user else None
    except jwt.InvalidTokenError:
        return None


def get_current_user(request: Request):
    user = authenticate_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def init_auth_db():
    with auth_connection() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, role TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT)")
        connection.execute("CREATE TABLE IF NOT EXISTS login_attempts (identifier TEXT PRIMARY KEY, count INTEGER NOT NULL, locked_until TEXT, updated_at TEXT NOT NULL)")

        generated_creds = []
        for prefix, role, name, def_email in DEFAULT_USERS:
            email = os.environ.get(f"{prefix}_EMAIL", def_email).strip().lower()
            env_pass = os.environ.get(f"{prefix}_PASSWORD")

            existing = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if not existing:
                password = env_pass or secrets.token_urlsafe(12)
                connection.execute(
                    "INSERT INTO users (id, email, name, role, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), email, name, role, hash_password(password), datetime.now(timezone.utc).isoformat())
                )
                generated_creds.append((role.upper(), email, password, "ENV" if env_pass else "AUTO_GENERATED"))
            elif env_pass and not verify_password(env_pass, existing["password_hash"]):
                connection.execute(
                    "UPDATE users SET role = ?, password_hash = ?, updated_at = ? WHERE email = ?",
                    (role, hash_password(env_pass), datetime.now(timezone.utc).isoformat(), email)
                )

        connection.commit()

        if generated_creds:
            print("\n" + "=" * 80)
            print(" SPENDGUARD CONSOLE AUTHENTICATION INITIALIZED")
            print("=" * 80)
            for r, em, pw, src in generated_creds:
                print(f" [{r:<8}] Email: {em:<26} Password: {pw:<18} ({src})")
            print("=" * 80 + "\n")


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_auth_db()
    get_resources()
    yield

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="SpendGuard Trust Layer API", version="1.0.0", lifespan=lifespan)

frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def protect_console_api(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api"):
        path = path[4:] or "/"
    if request.method == "OPTIONS" or path.startswith("/auth") or path in {"/", "/health"} or path.startswith("/simulator") or path.startswith("/simulation"):
        return await call_next(request)
    if path == "/transactions/evaluate" and request.method == "POST":
        return await call_next(request)
    if request.method in SAFE_METHODS:
        return await call_next(request)

    user = authenticate_request(request)
    if not user:
        if os.environ.get("STRICT_AUTH", "false").lower() != "true":
            return await call_next(request)
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    if path.startswith("/admin") and user["role"] != "admin":
        return JSONResponse(status_code=403, content={"detail": "Admin role required"})
    if path.endswith("/verify") and user["role"] not in {"admin", "operator"}:
        return JSONResponse(status_code=403, content={"detail": "Operator role required"})
    if user["role"] == "viewer":
        return JSONResponse(status_code=403, content={"detail": "Viewer role is read-only"})
    return await call_next(request)


@app.post("/auth/login")
def login(request: Request, response: Response, body: LoginRequest):
    email = body.email.strip().lower()
    identifier = f"{request.client.host if request.client else 'unknown'}:{email}"
    now = datetime.now(timezone.utc)
    with auth_connection() as connection:
        attempt = connection.execute("SELECT * FROM login_attempts WHERE identifier = ?", (identifier,)).fetchone()
        if attempt and attempt["locked_until"] and datetime.fromisoformat(attempt["locked_until"]) > now:
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in 15 minutes.")
        user = find_user_by_email(email)
        if not user or not verify_password(body.password, user["password_hash"]):
            failed = (attempt["count"] if attempt else 0) + 1
            locked_until = (now + timedelta(minutes=15)).isoformat() if failed >= 5 else None
            connection.execute("INSERT INTO login_attempts (identifier, count, locked_until, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(identifier) DO UPDATE SET count = excluded.count, locked_until = excluded.locked_until, updated_at = excluded.updated_at", (identifier, failed, locked_until, now.isoformat()))
            connection.commit()
            raise HTTPException(status_code=401, detail="Invalid email or password")
        connection.execute("DELETE FROM login_attempts WHERE identifier = ?", (identifier,))
        connection.commit()
    set_auth_cookies(response, user)
    token = create_access_token(user)
    return {**public_user(user), "access_token": token}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"status": "ok"}


@app.get("/auth/me")
def me(user=Depends(get_current_user)):
    return user


@app.post("/auth/refresh")
def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
        user = find_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        response.set_cookie("access_token", create_access_token(user), httponly=True, secure=False, samesite="lax", max_age=900, path="/")
        new_token = create_access_token(user)
        return {**public_user(user), "access_token": new_token}
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


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
    simulate_sandbox_payment_capture,
    generate_sandbox_receipt,
    execute_checkout_settlement,
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
            order_id = order.get("id") if isinstance(order, dict) else getattr(order, "id", None)
            receipt.razorpay_order_id = order_id
            if order_id:
                payment = simulate_sandbox_payment_capture(
                    order_id=order_id,
                    amount=transaction.amount,
                    currency="INR",
                )
                settlement = generate_sandbox_receipt(
                    transaction_id=transaction.id,
                    order_id=order_id,
                    payment_id=payment["id"],
                    amount=transaction.amount,
                    merchant=transaction.merchant,
                    sku=transaction.actual_sku,
                )
                receipt.razorpay_payment_id = payment.get("id")
                receipt.captured_at = payment.get("captured_at")
                receipt.settlement_status = "SETTLED"
                receipt.settlement_receipt_token = settlement.get("signature_hash")
                if receipt.summary:
                    receipt.summary = f"{receipt.summary} Payment was captured and settled on card rails (Razorpay Payment ID: {payment.get('id')})."
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
            receipt.settlement_status = "HOLD_AUTHORIZED"

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
    razorpay_payment_id = None
    settlement_status = None
    captured_at = None
    settlement_receipt_token = None

    # 1. Capture hold on approval
    if body.approved:
        try:
            order = create_test_order(
                amount=amt,
                currency="INR",
                receipt_id=id,
            )
            razorpay_order_id = order.get("id") if isinstance(order, dict) else getattr(order, "id", None)
            if hold_id:
                cap_res = capture_payment_hold(hold_id=hold_id, amount=amt, transaction_id=id)
                razorpay_payment_id = cap_res.get("razorpay_payment_id")
                captured_at = cap_res.get("captured_at")
                settlement_status = "SETTLED"
                settlement_receipt_token = cap_res.get("settlement_receipt_token")
        except Exception as e:
            payment_error = str(e)
        resolve_escalation(id, action="approved")
    else:
        # 2. Void hold on denial
        if hold_id:
            try:
                void_res = void_payment_hold(hold_id=hold_id, reason="human_denied")
                settlement_status = void_res.get("settlement_status", "HOLD_VOIDED")
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
        razorpay_payment_id=razorpay_payment_id,
        settlement_status=settlement_status,
        captured_at=captured_at,
        settlement_receipt_token=settlement_receipt_token,
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


# -----------------------------------------------------------------------------
# Live Agent Red-Team Simulation Endpoints
# -----------------------------------------------------------------------------
from simulator.catalog_server import router as simulator_router, get_trap_catalog
from simulator.scorer import compute_simulation_metrics
from agent.shopping_agent import run_shopping_agent, MAX_BATCH_RUNS, MAX_DAILY_LLM_CALLS
from api.db import save_simulation_run, get_simulation_runs, get_simulation_run

app.include_router(simulator_router)

TASK_BANK_PATH = REPO_ROOT / "agent" / "task_bank.json"


def get_task_bank() -> List[Dict[str, Any]]:
    if TASK_BANK_PATH.exists():
        with open(TASK_BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


class SimulationRunRequest(BaseModel):
    task_id: Optional[str] = None  # None or 'all' for batch
    mode: Optional[str] = None     # 'live_llm' or 'fallback_rule_based'


@app.get("/simulation/tasks")
def list_simulation_tasks():
    """Returns the benchmark task bank with difficulty and trap types."""
    return get_task_bank()


@app.post("/simulation/run")
def trigger_simulation_run(body: Optional[SimulationRunRequest] = None):
    """Executes a single simulation task or full adversarial batch."""
    mandates, intents, catalog, risk_model = get_resources()
    tasks = get_task_bank()
    if not tasks:
        raise HTTPException(status_code=404, detail="Task bank is empty or not found.")

    task_id = body.task_id if body else None
    preferred_mode = body.mode if body else None

    target_tasks = tasks
    if task_id and task_id.lower() != "all":
        target_tasks = [t for t in tasks if t["task_id"] == task_id]
        if not target_tasks:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found in task bank.")

    # Budget Guard Check
    if len(target_tasks) > MAX_BATCH_RUNS:
        raise HTTPException(
            status_code=400,
            detail=f"Requested batch size ({len(target_tasks)}) exceeds safety ceiling of {MAX_BATCH_RUNS} runs per batch.",
        )

    results = []
    for t in target_tasks:
        run_data = run_shopping_agent(
            task=t,
            mandates_map=mandates,
            intents_map=intents,
            risk_model=risk_model,
            preferred_mode=preferred_mode,
        )
        save_simulation_run(run_data)
        results.append(run_data)

    metrics = compute_simulation_metrics(results)
    return {
        "status": "ok",
        "count": len(results),
        "metrics": metrics,
        "runs": results,
    }


@app.get("/simulation/runs")
def list_all_simulation_runs(execution_mode: Optional[str] = None):
    """Lists historical simulation runs with optional execution_mode filter."""
    return get_simulation_runs(execution_mode=execution_mode)


@app.get("/simulation/runs/{run_id}")
def get_single_simulation_run(run_id: str):
    """Retrieves full transcript and telemetry for a specific simulation run."""
    run = get_simulation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Simulation run '{run_id}' not found.")
    return run


@app.get("/simulation/metrics")
def get_simulation_metrics(execution_mode: Optional[str] = None):
    """Computes headline red-team security metrics across historical simulation runs."""
    runs = get_simulation_runs(execution_mode=execution_mode)
    return compute_simulation_metrics(runs, execution_mode=execution_mode)

