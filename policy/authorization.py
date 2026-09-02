import unicodedata
from datetime import datetime, time, timedelta, timezone
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from data.schema import TransactionRequest
from policy.schema import Mandate, TimeWindowRule


class AuthorizationResult(BaseModel):
    passed: bool
    failed_checks: List[str]
    is_stale: bool


def _normalize_merchant_name(name: str) -> str:
    """Normalize Unicode (NFKC), strip, and collapse whitespace for canonical comparison."""
    if not name:
        return ""
    nfkc = unicodedata.normalize("NFKC", str(name))
    return " ".join(nfkc.strip().lower().split())


def _parse_time(time_str: str) -> time:
    """Parse HH:MM or HH:MM:SS string to datetime.time."""
    parts = [int(p) for p in time_str.strip().split(":")]
    if len(parts) == 2:
        return time(hour=parts[0], minute=parts[1])
    elif len(parts) == 3:
        return time(hour=parts[0], minute=parts[1], second=parts[2])
    raise ValueError(f"Invalid time format: {time_str}")


def _is_time_in_window(t: time, start_str: str, end_str: str) -> bool:
    """Check if clock time t is within start_str and end_str."""
    start = _parse_time(start_str)
    end = _parse_time(end_str)
    if start <= end:
        return start <= t <= end
    else:
        # Crosses midnight (e.g., 22:00 to 06:00)
        return t >= start or t <= end


def _matches_time_windows(tx_dt: datetime, time_windows: List[TimeWindowRule]) -> bool:
    """Check if timestamp matches any TimeWindowRule (day-of-week + start/end)."""
    day_name = tx_dt.strftime("%A").lower()
    tx_time = tx_dt.time()
    for rule in time_windows:
        if rule.days_of_week:
            allowed_days = [d.strip().lower() for d in rule.days_of_week]
            if day_name not in allowed_days:
                continue
        if _is_time_in_window(tx_time, rule.start, rule.end):
            return True
    return False


def _get_period_timedelta(period_name: str) -> timedelta:
    """Map period key to timedelta."""
    p = period_name.lower().strip()
    if p in ("daily", "day", "24h"):
        return timedelta(days=1)
    elif p in ("weekly", "week", "7d"):
        return timedelta(days=7)
    elif p in ("monthly", "month", "30d"):
        return timedelta(days=30)
    return timedelta(days=1)


def check_authorization(
    transaction: TransactionRequest,
    mandate: Mandate,
    prior_transactions: Optional[List[Dict[str, Any]]] = None,
) -> AuthorizationResult:
    """
    Evaluates a transaction against a mandate under Pillar 1 (Authorization).
    
    Checks 1-5 are deterministic hard checks:
    1. Budget: amount > per_transaction_cap -> "budget_exceeded"
    2. Category: category not in categories -> "category_not_allowed"
    3. Merchant: canonical normalized merchant check -> "merchant_not_allowed"
    4. Time window: evaluated against mandate.time_windows list if present, else legacy start/end
    5. Cumulative Mandate Budget & Period Caps: checks total lifetime budget and periodic spend
    
    Check 6 (Mandate Freshness):
    - Evaluated against both transaction timestamp and authoritative server wall-clock time
    """
    failed_checks: List[str] = []

    # 0. Amount positivity check
    if transaction.amount <= 0:
        failed_checks.append("invalid_amount_non_positive")

    # 0.5 Agent-Mandate identity binding check
    if mandate.agent_id and transaction.agent_id and transaction.agent_id != mandate.agent_id:
        failed_checks.append("agent_mandate_mismatch")

    # 1. Budget check (per-transaction cap)
    if transaction.amount > mandate.per_transaction_cap:
        failed_checks.append("budget_exceeded")

    # 2. Category check
    if transaction.category not in mandate.categories:
        failed_checks.append("category_not_allowed")

    # 3. Merchant check with Unicode NFKC & whitespace normalization
    if mandate.merchants and len(mandate.merchants) > 0:
        norm_tx_merchant = _normalize_merchant_name(transaction.merchant)
        norm_allowed_merchants = {_normalize_merchant_name(m) for m in mandate.merchants}
        if norm_tx_merchant not in norm_allowed_merchants:
            failed_checks.append("merchant_not_allowed")

    # 4. Time window check (multi-window support with legacy fallback)
    if mandate.time_windows and len(mandate.time_windows) > 0:
        if not _matches_time_windows(transaction.timestamp, mandate.time_windows):
            failed_checks.append("outside_time_window")
    else:
        tx_time = transaction.timestamp.time()
        if not _is_time_in_window(tx_time, mandate.time_window_start, mandate.time_window_end):
            failed_checks.append("outside_time_window")

    # 5. Cumulative Mandate Budget & Period Caps
    priors = prior_transactions
    if priors is None:
        try:
            from api.db import get_transactions
            priors = get_transactions(mandate_id=mandate.id)
        except Exception:
            priors = []

    # 5a. Total Mandate Lifetime Budget (cross-session cap)
    if mandate.total_mandate_budget and mandate.total_mandate_budget > 0:
        total_mandate_spend = sum(
            float(p.get("amount", 0.0))
            for p in priors
            if p.get("decision") != "BLOCK" and p.get("mandate_id") == mandate.id
        )
        if total_mandate_spend + transaction.amount > mandate.total_mandate_budget + 0.01:
            failed_checks.append("mandate_total_budget_exceeded")

    # 5b. Cumulative Period Caps check (if period_caps specified)
    if mandate.period_caps and len(mandate.period_caps) > 0:
        tx_ts = transaction.timestamp
        for period, cap in mandate.period_caps.items():
            window_span = _get_period_timedelta(period)
            cutoff = tx_ts - window_span
            
            period_sum = 0.0
            for p in priors:
                if p.get("decision") == "BLOCK":
                    continue
                p_ts_raw = p.get("timestamp")
                if isinstance(p_ts_raw, str):
                    try:
                        p_ts = datetime.fromisoformat(p_ts_raw)
                    except Exception:
                        continue
                elif isinstance(p_ts_raw, datetime):
                    p_ts = p_ts_raw
                else:
                    continue

                # Ensure timezone alignment
                if p_ts.tzinfo is not None and tx_ts.tzinfo is None:
                    p_ts = p_ts.replace(tzinfo=None)
                elif p_ts.tzinfo is None and tx_ts.tzinfo is not None:
                    p_ts = p_ts.replace(tzinfo=tx_ts.tzinfo)

                if cutoff <= p_ts < tx_ts:
                    period_sum += float(p.get("amount", 0.0))

            if (period_sum + transaction.amount) > float(cap):
                failed_checks.append(f"period_cap_exceeded_{period}")

    # 6. Mandate freshness & timestamp validation
    tx_ts = transaction.timestamp
    mandate_issued = mandate.issued_at
    server_now = datetime.now(timezone.utc)

    # Normalize timezone awareness
    if tx_ts.tzinfo is not None and mandate_issued.tzinfo is None:
        mandate_issued = mandate_issued.replace(tzinfo=tx_ts.tzinfo)
    elif tx_ts.tzinfo is None and mandate_issued.tzinfo is not None:
        tx_ts = tx_ts.replace(tzinfo=mandate_issued.tzinfo)

    expiry_time = mandate_issued + timedelta(seconds=mandate.ttl_seconds)
    is_stale = tx_ts > expiry_time

    # Timestamp sanity: Check for extreme future clock drift (> 1 year into future) or extreme backdating (> 60 days before mandate issuance)
    if (mandate_issued - tx_ts) > timedelta(days=60):
        failed_checks.append("timestamp_predates_mandate_issuance")

    if (tx_ts - mandate_issued) > timedelta(days=365):
        failed_checks.append("timestamp_future_drift_exceeded")

    passed = len(failed_checks) == 0

    return AuthorizationResult(
        passed=passed,
        failed_checks=failed_checks,
        is_stale=is_stale,
    )
