from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

SOURCE_HIERARCHY: Dict[str, int] = {
    "checkout_sku": 4,
    "merchant_structured_spec": 3,
    "catalog_spec": 2,
    "agent_claim": 1,
}

DEFAULT_TTLS: Dict[str, int] = {
    "price": 3600,                    # 1 hour
    "checkout_sku": 1800,             # 30 minutes
    "merchant_structured_spec": 86400,# 24 hours
    "catalog_spec": 2592000,          # 30 days
}


class EvidenceSourceRecord(BaseModel):
    source: str
    field: str
    value: Any
    retrieved_at: datetime
    ttl_seconds: Optional[int] = None


def get_source_rank(source: str) -> int:
    """Returns the priority rank of an evidence source (higher = more authoritative)."""
    return SOURCE_HIERARCHY.get(source.lower().strip(), 0)


def is_record_fresh(record: EvidenceSourceRecord, current_time: Optional[datetime] = None) -> bool:
    """Checks whether an evidence source record is within its TTL validity window."""
    now = current_time or datetime.now(timezone.utc)
    retrieved = record.retrieved_at

    # Normalize timezone
    if retrieved.tzinfo is None and now.tzinfo is not None:
        retrieved = retrieved.replace(tzinfo=now.tzinfo)
    elif retrieved.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=retrieved.tzinfo)

    ttl = record.ttl_seconds
    if ttl is None:
        if record.field == "price":
            ttl = DEFAULT_TTLS["price"]
        else:
            ttl = DEFAULT_TTLS.get(record.source, 86400)

    expiry = retrieved + timedelta(seconds=ttl)
    return now <= expiry


def resolve_source_records(
    records: List[EvidenceSourceRecord],
    current_time: Optional[datetime] = None,
) -> Dict[str, EvidenceSourceRecord]:
    """
    Groups evidence records by field and resolves conflicting values by choosing
    the highest-priority fresh source.
    """
    now = current_time or datetime.now(timezone.utc)
    by_field: Dict[str, List[EvidenceSourceRecord]] = {}
    for r in records:
        if r.field not in by_field:
            by_field[r.field] = []
        by_field[r.field].append(r)

    resolved: Dict[str, EvidenceSourceRecord] = {}
    for field, field_records in by_field.items():
        # Sort by source rank descending, then retrieved_at descending
        sorted_records = sorted(
            field_records,
            key=lambda rec: (get_source_rank(rec.source), rec.retrieved_at),
            reverse=True,
        )
        resolved[field] = sorted_records[0]

    return resolved
