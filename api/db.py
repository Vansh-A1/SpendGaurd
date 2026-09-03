import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "spendguard.db"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        mandate_id TEXT NOT NULL,
        user_intent_id TEXT NOT NULL,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        merchant TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        claimed_product_json TEXT NOT NULL,
        actual_sku TEXT NOT NULL,
        authorization_json TEXT NOT NULL,
        intent_fidelity_json TEXT NOT NULL,
        behavioral_risk_json TEXT NOT NULL,
        evidence_json TEXT NOT NULL,
        decision TEXT NOT NULL,
        decision_reason TEXT NOT NULL,
        razorpay_order_id TEXT,
        payment_hold_id TEXT,
        payment_hold_status TEXT,
        session_id TEXT,
        intent_version INTEGER DEFAULT 1,
        goal_drift_json TEXT,
        trust_snapshot_json TEXT,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS provenance_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        prev_hash TEXT,
        event_hash TEXT,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trust_snapshots (
        trust_snapshot_id TEXT PRIMARY KEY,
        transaction_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        mandate_id TEXT NOT NULL,
        mandate_version INTEGER NOT NULL DEFAULT 1,
        intent_id TEXT NOT NULL,
        intent_version INTEGER NOT NULL DEFAULT 1,
        purchase_session_id TEXT,
        selected_sku TEXT NOT NULL,
        amount REAL NOT NULL,
        decision TEXT NOT NULL,
        decision_reason TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS escalations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT NOT NULL UNIQUE,
        agent_id TEXT NOT NULL,
        amount REAL NOT NULL,
        sla_minutes INTEGER NOT NULL DEFAULT 15,
        status TEXT NOT NULL,
        payment_hold_id TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_holds (
        hold_id TEXT PRIMARY KEY,
        transaction_id TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL,
        status TEXT NOT NULL,
        razorpay_order_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    );
    """)

    # Migration checks for existing databases
    cursor.execute("PRAGMA table_info(transactions)")
    tx_cols = [row[1] for row in cursor.fetchall()]
    if "session_id" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN session_id TEXT")
    if "intent_version" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN intent_version INTEGER DEFAULT 1")
    if "goal_drift_json" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN goal_drift_json TEXT")
    if "trust_snapshot_json" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN trust_snapshot_json TEXT")
    if "payment_hold_id" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN payment_hold_id TEXT")
    if "payment_hold_status" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN payment_hold_status TEXT")
    if "summary" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN summary TEXT")
    if "razorpay_payment_id" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN razorpay_payment_id TEXT")
    if "captured_at" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN captured_at TEXT")
    if "settlement_status" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN settlement_status TEXT")
    if "settlement_receipt_token" not in tx_cols:
        cursor.execute("ALTER TABLE transactions ADD COLUMN settlement_receipt_token TEXT")

    cursor.execute("PRAGMA table_info(provenance_events)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if "prev_hash" not in existing_cols:
        cursor.execute("ALTER TABLE provenance_events ADD COLUMN prev_hash TEXT")
    if "event_hash" not in existing_cols:
        cursor.execute("ALTER TABLE provenance_events ADD COLUMN event_hash TEXT")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (transaction_id) REFERENCES transactions (id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS simulation_runs (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        task_prompt TEXT NOT NULL,
        difficulty TEXT,
        trap_type TEXT NOT NULL,
        selected_sku TEXT,
        selected_product_name TEXT,
        amount REAL,
        execution_mode TEXT NOT NULL,
        model_name TEXT,
        agent_fooled INTEGER NOT NULL,
        initial_decision TEXT NOT NULL,
        resolved_decision TEXT NOT NULL,
        is_true_leakage INTEGER NOT NULL,
        reviewer_action TEXT,
        decision_reason TEXT,
        transcript_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("PRAGMA table_info(simulation_runs)")
    sim_cols = [row[1] for row in cursor.fetchall()]
    if "model_name" not in sim_cols:
        cursor.execute("ALTER TABLE simulation_runs ADD COLUMN model_name TEXT")

    conn.commit()
    conn.close()


# Ensure tables are initialized on import
init_db()


def save_transaction_evaluation(
    tx_dict: Dict[str, Any],
    receipt_dict: Dict[str, Any],
    actor: str = "system",
    db_path: Optional[Path] = None,
):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    def _serialize_pillar(val: Any) -> str:
        if val is None or val == "skipped":
            return "skipped"
        if isinstance(val, str):
            return val
        if hasattr(val, "model_dump"):
            return json.dumps(val.model_dump(mode="json"))
        if isinstance(val, dict):
            return json.dumps(val)
        return json.dumps(val)

    auth_json = _serialize_pillar(receipt_dict.get("authorization", "skipped"))
    intent_json = _serialize_pillar(receipt_dict.get("intent_fidelity", "skipped"))
    risk_json = _serialize_pillar(receipt_dict.get("behavioral_risk", "skipped"))
    evidence_json = _serialize_pillar(receipt_dict.get("evidence", "skipped"))
    drift_json = _serialize_pillar(receipt_dict.get("goal_drift", "skipped"))

    snap_obj = receipt_dict.get("trust_snapshot")
    snap_json = None
    if snap_obj is not None:
        if hasattr(snap_obj, "model_dump"):
            snap_json = json.dumps(snap_obj.model_dump(mode="json"))
        elif isinstance(snap_obj, dict):
            snap_json = json.dumps(snap_obj)
        else:
            snap_json = str(snap_obj)

    claimed_product_json = (
        json.dumps(tx_dict.get("claimed_product", {}))
        if isinstance(tx_dict.get("claimed_product"), dict)
        else str(tx_dict.get("claimed_product", "{}"))
    )

    session_id = tx_dict.get("session_id")
    intent_version = tx_dict.get("intent_version", 1)
    payment_hold_id = receipt_dict.get("payment_hold_id")
    payment_hold_status = receipt_dict.get("payment_hold_status")

    cursor.execute("""
    INSERT OR REPLACE INTO transactions (
        id, agent_id, mandate_id, user_intent_id, amount, category, merchant, timestamp,
        claimed_product_json, actual_sku, authorization_json, intent_fidelity_json,
        behavioral_risk_json, evidence_json, decision, decision_reason, razorpay_order_id,
        payment_hold_id, payment_hold_status, session_id, intent_version, goal_drift_json,
        trust_snapshot_json, summary, razorpay_payment_id, captured_at, settlement_status,
        settlement_receipt_token, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        tx_dict["id"],
        tx_dict["agent_id"],
        tx_dict["mandate_id"],
        tx_dict["user_intent_id"],
        float(tx_dict["amount"]),
        tx_dict["category"],
        tx_dict["merchant"],
        str(tx_dict["timestamp"]),
        claimed_product_json,
        tx_dict["actual_sku"],
        auth_json,
        intent_json,
        risk_json,
        evidence_json,
        receipt_dict["decision"],
        receipt_dict["decision_reason"],
        receipt_dict.get("razorpay_order_id"),
        payment_hold_id,
        payment_hold_status,
        session_id,
        intent_version,
        drift_json,
        snap_json,
        receipt_dict.get("summary"),
        receipt_dict.get("razorpay_payment_id"),
        receipt_dict.get("captured_at"),
        receipt_dict.get("settlement_status"),
        receipt_dict.get("settlement_receipt_token"),
        now_iso,
    ))

    # Clear and insert TrustSnapshot if present
    if snap_obj is not None:
        snap_dict = snap_obj.model_dump(mode="json") if hasattr(snap_obj, "model_dump") else (snap_obj if isinstance(snap_obj, dict) else {})
        snap_id = snap_dict.get("trust_snapshot_id", f"snap_{tx_dict['id']}")
        cursor.execute("DELETE FROM trust_snapshots WHERE transaction_id = ?", (tx_dict["id"],))
        cursor.execute("""
        INSERT INTO trust_snapshots (
            trust_snapshot_id, transaction_id, agent_id, mandate_id, mandate_version,
            intent_id, intent_version, purchase_session_id, selected_sku, amount,
            decision, decision_reason, snapshot_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snap_id,
            tx_dict["id"],
            tx_dict["agent_id"],
            tx_dict["mandate_id"],
            snap_dict.get("mandate_version", 1),
            tx_dict["user_intent_id"],
            intent_version,
            session_id,
            tx_dict["actual_sku"],
            float(tx_dict["amount"]),
            receipt_dict["decision"],
            receipt_dict["decision_reason"],
            snap_json,
            now_iso,
        ))

    # Clear prior provenance events if replacing
    cursor.execute("DELETE FROM provenance_events WHERE transaction_id = ?", (tx_dict["id"],))

    # Insert provenance events
    for event in receipt_dict.get("provenance_trail", []):
        payload_str = json.dumps(event.get("payload", {})) if isinstance(event.get("payload"), dict) else str(event.get("payload", "{}"))
        cursor.execute("""
        INSERT INTO provenance_events (transaction_id, seq, event_type, payload_json, prev_hash, event_hash)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tx_dict["id"],
            event.get("seq", 1),
            event.get("event_type", "event"),
            payload_str,
            event.get("prev_hash"),
            event.get("event_hash"),
        ))

    # Insert audit log
    cursor.execute("""
    INSERT INTO audit_log (transaction_id, actor, action, timestamp)
    VALUES (?, ?, ?, ?)
    """, (tx_dict["id"], actor, receipt_dict["decision"], now_iso))

    conn.commit()
    conn.close()


def get_transactions(
    decision: Optional[str] = None,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
    mandate_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if decision:
        query += " AND decision = ?"
        params.append(decision)
    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)
    if session_id:
        query += " AND session_id = ?"
        params.append(session_id)
    if mandate_id:
        query += " AND mandate_id = ?"
        params.append(mandate_id)

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_transaction_receipt(
    transaction_id: str, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,))
    tx_row = cursor.fetchone()
    if not tx_row:
        conn.close()
        return None

    tx = dict(tx_row)

    # Get provenance trail
    cursor.execute(
        "SELECT * FROM provenance_events WHERE transaction_id = ? ORDER BY seq ASC",
        (transaction_id,),
    )
    events_rows = cursor.fetchall()
    provenance_trail = []
    for er in events_rows:
        provenance_trail.append({
            "seq": er["seq"],
            "event_type": er["event_type"],
            "payload": json.loads(er["payload_json"]),
            "prev_hash": er["prev_hash"] if "prev_hash" in er.keys() else None,
            "event_hash": er["event_hash"] if "event_hash" in er.keys() else None,
        })

    # Parse pillar JSONs
    def _parse_pillar(json_val: Optional[str]):
        if not json_val or json_val == "skipped":
            return "skipped"
        try:
            return json.loads(json_val)
        except Exception:
            return json_val

    receipt = {
        **tx,
        "transaction_id": tx["id"],
        "claimed_product": _parse_pillar(tx.get("claimed_product_json")),
        "authorization": _parse_pillar(tx["authorization_json"]),
        "intent_fidelity": _parse_pillar(tx["intent_fidelity_json"]),
        "behavioral_risk": _parse_pillar(tx["behavioral_risk_json"]),
        "evidence": _parse_pillar(tx["evidence_json"]),
        "goal_drift": _parse_pillar(tx.get("goal_drift_json")),
        "provenance_trail": provenance_trail,
        "decision": tx["decision"],
        "decision_reason": tx["decision_reason"],
        "summary": tx.get("summary"),
        "trust_snapshot": _parse_pillar(tx.get("trust_snapshot_json")),
        "session_id": tx.get("session_id"),
        "intent_version": tx.get("intent_version", 1),
        "payment_hold_id": tx.get("payment_hold_id"),
        "payment_hold_status": tx.get("payment_hold_status"),
        "razorpay_order_id": tx.get("razorpay_order_id"),
        "razorpay_payment_id": tx.get("razorpay_payment_id"),
        "captured_at": tx.get("captured_at"),
        "settlement_status": tx.get("settlement_status"),
        "settlement_receipt_token": tx.get("settlement_receipt_token"),
    }
    conn.close()
    return receipt


def get_trust_snapshot(transaction_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trust_snapshots WHERE transaction_id = ?", (transaction_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        r_dict = dict(row)
        return json.loads(r_dict["snapshot_json"])
    return None


def update_transaction_decision(
    transaction_id: str,
    new_decision: str,
    actor: str,
    action: str,
    reason: str,
    razorpay_order_id: Optional[str] = None,
    razorpay_payment_id: Optional[str] = None,
    settlement_status: Optional[str] = None,
    captured_at: Optional[str] = None,
    settlement_receipt_token: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> bool:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    updates = ["decision = ?", "decision_reason = ?"]
    params = [new_decision, reason]

    if razorpay_order_id:
        updates.append("razorpay_order_id = ?")
        params.append(razorpay_order_id)
    if razorpay_payment_id:
        updates.append("razorpay_payment_id = ?")
        params.append(razorpay_payment_id)
    if settlement_status:
        updates.append("settlement_status = ?")
        params.append(settlement_status)
    if captured_at:
        updates.append("captured_at = ?")
        params.append(captured_at)
    if settlement_receipt_token:
        updates.append("settlement_receipt_token = ?")
        params.append(settlement_receipt_token)

    params.append(transaction_id)
    query = f"UPDATE transactions SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)

    if cursor.rowcount == 0:
        conn.close()
        return False

    cursor.execute("""
    INSERT INTO audit_log (transaction_id, actor, action, timestamp)
    VALUES (?, ?, ?, ?)
    """, (transaction_id, actor, action, now_iso))

    conn.commit()
    conn.close()
    return True


def get_audit_logs(transaction_id: Optional[str] = None, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if transaction_id:
        cursor.execute("SELECT * FROM audit_log WHERE transaction_id = ? ORDER BY id ASC", (transaction_id,))
    else:
        cursor.execute("SELECT * FROM audit_log ORDER BY id ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def save_simulation_run(run_dict: Dict[str, Any], db_path: Optional[Path] = None):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO simulation_runs (
        id, task_id, task_prompt, difficulty, trap_type, selected_sku, selected_product_name,
        amount, execution_mode, model_name, agent_fooled, initial_decision, resolved_decision,
        is_true_leakage, reviewer_action, decision_reason, transcript_json, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_dict["id"],
        run_dict["task_id"],
        run_dict["task_prompt"],
        run_dict.get("difficulty", "medium"),
        run_dict["trap_type"],
        run_dict.get("selected_sku"),
        run_dict.get("selected_product_name"),
        float(run_dict.get("amount", 0)),
        run_dict.get("execution_mode", "fallback_rule_based"),
        run_dict.get("model_name"),
        1 if run_dict.get("agent_fooled") else 0,
        run_dict["initial_decision"],
        run_dict["resolved_decision"],
        1 if run_dict.get("is_true_leakage") else 0,
        run_dict.get("reviewer_action"),
        run_dict.get("decision_reason"),
        json.dumps(run_dict.get("transcript", [])),
        run_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
    ))
    conn.commit()
    conn.close()


def get_simulation_runs(execution_mode: Optional[str] = None, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    if execution_mode and execution_mode.lower() != "all":
        cursor.execute("SELECT * FROM simulation_runs WHERE execution_mode = ? ORDER BY created_at DESC", (execution_mode,))
    else:
        cursor.execute("SELECT * FROM simulation_runs ORDER BY created_at DESC")
    rows = cursor.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        d["agent_fooled"] = bool(d["agent_fooled"])
        d["is_true_leakage"] = bool(d["is_true_leakage"])
        try:
            d["transcript"] = json.loads(d["transcript_json"])
        except Exception:
            d["transcript"] = []
        results.append(d)
    conn.close()
    return results


def get_simulation_run(run_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM simulation_runs WHERE id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["agent_fooled"] = bool(d["agent_fooled"])
    d["is_true_leakage"] = bool(d["is_true_leakage"])
    try:
        d["transcript"] = json.loads(d["transcript_json"])
    except Exception:
        d["transcript"] = []
    return d

