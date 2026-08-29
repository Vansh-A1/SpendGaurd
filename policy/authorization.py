from datetime import datetime, time, timedelta
from typing import List
from pydantic import BaseModel

from data.schema import TransactionRequest
from policy.schema import Mandate


class AuthorizationResult(BaseModel):
    passed: bool
    failed_checks: List[str]
    is_stale: bool


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


def check_authorization(transaction: TransactionRequest, mandate: Mandate) -> AuthorizationResult:
    """
    Evaluates a transaction against a mandate under Pillar 1 (Authorization).
    
    Checks 1-4 are deterministic hard checks:
    1. Budget: amount > per_transaction_cap -> "budget_exceeded"
    2. Category: category not in categories -> "category_not_allowed"
    3. Merchant: if merchants non-empty, merchant not in merchants -> "merchant_not_allowed"
    4. Time window: timestamp's time outside window -> "outside_time_window"
    
    Check 5 (Mandate Freshness):
    - If timestamp > issued_at + ttl_seconds -> is_stale=True (does not cause passed to fail here)
    """
    failed_checks: List[str] = []

    # 1. Budget check
    if transaction.amount > mandate.per_transaction_cap:
        failed_checks.append("budget_exceeded")

    # 2. Category check
    if transaction.category not in mandate.categories:
        failed_checks.append("category_not_allowed")

    # 3. Merchant check
    if mandate.merchants and transaction.merchant not in mandate.merchants:
        failed_checks.append("merchant_not_allowed")

    # 4. Time window check
    tx_time = transaction.timestamp.time()
    if not _is_time_in_window(tx_time, mandate.time_window_start, mandate.time_window_end):
        failed_checks.append("outside_time_window")

    # 5. Mandate freshness check (separate flag, does not fail passed)
    tx_ts = transaction.timestamp
    mandate_issued = mandate.issued_at

    # Normalize timezone awareness if needed
    if tx_ts.tzinfo is not None and mandate_issued.tzinfo is None:
        mandate_issued = mandate_issued.replace(tzinfo=tx_ts.tzinfo)
    elif tx_ts.tzinfo is None and mandate_issued.tzinfo is not None:
        tx_ts = tx_ts.replace(tzinfo=mandate_issued.tzinfo)

    expiry_time = mandate_issued + timedelta(seconds=mandate.ttl_seconds)
    is_stale = tx_ts > expiry_time

    passed = len(failed_checks) == 0

    return AuthorizationResult(
        passed=passed,
        failed_checks=failed_checks,
        is_stale=is_stale,
    )
