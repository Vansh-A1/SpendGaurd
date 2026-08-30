import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from api.db import get_db_connection, update_transaction_decision
from payments.razorpay_client import void_payment_hold

DEFAULT_SLA_MINUTES = 15
_WEBHOOK_CONFIG: Dict[str, Optional[str]] = {"url": None}


def register_webhook(url: str):
    """Configures the endpoint URL for escalation webhooks."""
    _WEBHOOK_CONFIG["url"] = url


def get_webhook_url() -> Optional[str]:
    """Returns the currently configured webhook URL, if any."""
    return _WEBHOOK_CONFIG.get("url")


def clear_webhooks():
    """Resets webhook configuration."""
    _WEBHOOK_CONFIG["url"] = None


def dispatch_escalation_webhook(
    transaction_data: Dict[str, Any],
    receipt_data: Dict[str, Any],
    webhook_url: Optional[str] = None,
) -> bool:
    """
    Dispatches a lightweight HTTP POST webhook on creation of a VERIFY escalation.
    Non-blocking / resilient to network errors.
    """
    target_url = webhook_url or get_webhook_url()
    if not target_url:
        return False

    payload = {
        "event": "transaction_escalated_for_verification",
        "transaction_id": transaction_data.get("id"),
        "agent_id": transaction_data.get("agent_id"),
        "amount": transaction_data.get("amount"),
        "category": transaction_data.get("category"),
        "merchant": transaction_data.get("merchant"),
        "decision": receipt_data.get("decision"),
        "decision_reason": receipt_data.get("decision_reason"),
        "payment_hold_id": receipt_data.get("payment_hold_id"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            target_url,
            data=req_data,
            headers={"Content-Type": "application/json", "User-Agent": "SpendGuard-Escalation-Engine/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return 200 <= resp.status < 300
    except Exception:
        # Graceful failure: webhooks should not disrupt transaction evaluation flow
        return False


def create_escalation(
    transaction_id: str,
    agent_id: str,
    amount: float,
    sla_minutes: int = DEFAULT_SLA_MINUTES,
    payment_hold_id: Optional[str] = None,
    current_time: Optional[datetime] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Registers a new human verification item in the escalation queue with a strict SLA deadline.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    now = current_time or datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=sla_minutes)

    now_iso = now.isoformat()
    expires_iso = expires_at.isoformat()

    cursor.execute("""
    INSERT OR REPLACE INTO escalations (
        transaction_id, agent_id, amount, sla_minutes, status,
        payment_hold_id, created_at, expires_at, resolved_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
    """, (
        transaction_id,
        agent_id,
        float(amount),
        sla_minutes,
        "pending",
        payment_hold_id,
        now_iso,
        expires_iso,
    ))

    conn.commit()
    conn.close()

    return {
        "transaction_id": transaction_id,
        "agent_id": agent_id,
        "amount": float(amount),
        "sla_minutes": sla_minutes,
        "status": "pending",
        "payment_hold_id": payment_hold_id,
        "created_at": now_iso,
        "expires_at": expires_iso,
    }


def get_pending_escalations(
    db_path: Optional[Path] = None,
    current_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Returns all active pending items in the escalation queue along with remaining SLA seconds.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM escalations WHERE status = 'pending' ORDER BY expires_at ASC
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    now = current_time or datetime.now(timezone.utc)
    for r in rows:
        exp_dt = datetime.fromisoformat(r["expires_at"])
        remaining = (exp_dt - now).total_seconds()
        r["remaining_seconds"] = max(0.0, remaining)
        r["is_expired"] = remaining <= 0.0

    return rows


def resolve_escalation(
    transaction_id: str,
    action: str,  # 'approved' or 'denied'
    db_path: Optional[Path] = None,
    current_time: Optional[datetime] = None,
) -> bool:
    """
    Marks an escalation item as resolved ('approved' or 'denied').
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    now_iso = (current_time or datetime.now(timezone.utc)).isoformat()
    status = "approved" if action == "approved" else "denied"

    cursor.execute("""
    UPDATE escalations
    SET status = ?, resolved_at = ?
    WHERE transaction_id = ?
    """, (status, now_iso, transaction_id))

    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success


def process_escalation_timeouts(
    db_path: Optional[Path] = None,
    current_time: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Scans the escalation queue for items that have exceeded their SLA timeout without human action.
    Applies the default fallback: auto-deny transaction (BLOCK) and void the payment hold.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM escalations WHERE status = 'pending'
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    now = current_time or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    timed_out_items = []

    for r in rows:
        exp_dt = datetime.fromisoformat(r["expires_at"])
        if now >= exp_dt:
            tx_id = r["transaction_id"]
            hold_id = r.get("payment_hold_id")

            # 1. Update transaction decision in DB to BLOCK
            update_transaction_decision(
                transaction_id=tx_id,
                new_decision="BLOCK",
                actor="system_sla_watchdog",
                action="sla_timeout_auto_denied",
                reason=f"blocked: escalation SLA timeout expired ({r['sla_minutes']}m auto-denial)",
                db_path=db_path,
            )

            # 2. Void associated payment hold
            if hold_id:
                void_payment_hold(hold_id, reason="sla_timeout")

            # 3. Update escalation status in DB
            conn = get_db_connection(db_path)
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE escalations
            SET status = 'timed_out', resolved_at = ?
            WHERE transaction_id = ?
            """, (now_iso, tx_id))
            conn.commit()
            conn.close()

            timed_out_items.append({
                "transaction_id": tx_id,
                "agent_id": r["agent_id"],
                "amount": r["amount"],
                "sla_minutes": r["sla_minutes"],
                "payment_hold_id": hold_id,
                "action_taken": "auto_denied_and_hold_voided",
                "timed_out_at": now_iso,
            })

    return timed_out_items
