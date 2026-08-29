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

    # Migration check: ensure prev_hash and event_hash exist on existing tables
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

    claimed_product_json = (
        json.dumps(tx_dict.get("claimed_product", {}))
        if isinstance(tx_dict.get("claimed_product"), dict)
        else str(tx_dict.get("claimed_product", "{}"))
    )

    cursor.execute("""
    INSERT OR REPLACE INTO transactions (
        id, agent_id, mandate_id, user_intent_id, amount, category, merchant, timestamp,
        claimed_product_json, actual_sku, authorization_json, intent_fidelity_json,
        behavioral_risk_json, evidence_json, decision, decision_reason, razorpay_order_id, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    db_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = "SELECT * FROM transactions"
    params = []
    conditions = []

    if decision:
        conditions.append("decision = ?")
        params.append(decision.upper())
    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY created_at DESC, timestamp DESC"

    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_transaction_receipt(transaction_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
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
    def _parse_pillar(json_val: str):
        if json_val == "skipped":
            return "skipped"
        try:
            return json.loads(json_val)
        except Exception:
            return json_val

    receipt = {
        "transaction_id": tx["id"],
        "authorization": _parse_pillar(tx["authorization_json"]),
        "intent_fidelity": _parse_pillar(tx["intent_fidelity_json"]),
        "behavioral_risk": _parse_pillar(tx["behavioral_risk_json"]),
        "evidence": _parse_pillar(tx["evidence_json"]),
        "provenance_trail": provenance_trail,
        "decision": tx["decision"],
        "decision_reason": tx["decision_reason"],
        "razorpay_order_id": tx.get("razorpay_order_id"),
    }
    conn.close()
    return receipt


def update_transaction_decision(
    transaction_id: str,
    new_decision: str,
    actor: str,
    action: str,
    reason: str,
    razorpay_order_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> bool:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()

    if razorpay_order_id:
        cursor.execute(
            "UPDATE transactions SET decision = ?, decision_reason = ?, razorpay_order_id = ? WHERE id = ?",
            (new_decision, reason, razorpay_order_id, transaction_id),
        )
    else:
        cursor.execute(
            "UPDATE transactions SET decision = ?, decision_reason = ? WHERE id = ?",
            (new_decision, reason, transaction_id),
        )

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
