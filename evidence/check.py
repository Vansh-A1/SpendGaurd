from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from data.schema import Product
from evidence.sources import EvidenceSourceRecord, is_record_fresh, resolve_source_records, get_source_rank


class EvidenceDetail(BaseModel):
    field: str
    source: str
    observed_value: Any
    retrieved_at: datetime
    is_fresh: bool


class EvidenceResult(BaseModel):
    conflicts: List[Dict[str, Any]]
    sources_checked: List[str]
    evidence_details: Optional[List[EvidenceDetail]] = None


def _match_val(claimed_val: Any, actual_val: Any, field_name: str) -> bool:
    """Compare claimed value with actual catalog value."""
    if field_name == "price" or (
        isinstance(claimed_val, (int, float))
        and isinstance(actual_val, (int, float))
        and not isinstance(claimed_val, bool)
        and not isinstance(actual_val, bool)
    ):
        # Price tolerance check: within 1%
        c_num = float(claimed_val)
        a_num = float(actual_val)
        if a_num == 0:
            return c_num == 0
        return abs(c_num - a_num) / a_num <= 0.01

    if isinstance(claimed_val, str) and isinstance(actual_val, str):
        return claimed_val.strip().lower() == actual_val.strip().lower()

    return claimed_val == actual_val


def check_evidence(
    claimed_product: Dict[str, Any],
    actual_sku: str,
    catalog: List[Product],
    multi_source_records: Optional[List[EvidenceSourceRecord]] = None,
    current_time: Optional[datetime] = None,
) -> EvidenceResult:
    """
    Verifies agent claims about a product against trusted merchant/catalog ground truth.
    Supports multi-source evidence resolution and TTL freshness checks.
    """
    sources_checked: List[str] = ["catalog_spec"]
    conflicts: List[Dict[str, Any]] = []
    evidence_details: List[EvidenceDetail] = []
    now = current_time or datetime.now(timezone.utc)

    # 1. Multi-source records resolution if provided
    resolved_sources: Dict[str, EvidenceSourceRecord] = {}
    if multi_source_records and len(multi_source_records) > 0:
        for rec in multi_source_records:
            if rec.source not in sources_checked:
                sources_checked.append(rec.source)
            fresh = is_record_fresh(rec, now)
            evidence_details.append(
                EvidenceDetail(
                    field=rec.field,
                    source=rec.source,
                    observed_value=rec.value,
                    retrieved_at=rec.retrieved_at,
                    is_fresh=fresh,
                )
            )
            # Flag stale records as evidence conflicts
            if not fresh:
                claimed_v = claimed_product.get(rec.field, claimed_product.get("specs", {}).get(rec.field))
                conflicts.append({
                    "field": rec.field,
                    "claimed": claimed_v,
                    "actual": "stale_evidence",
                    "source": rec.source,
                    "reason": "source_ttl_expired",
                })

        resolved_sources = resolve_source_records(
            [r for r in multi_source_records if is_record_fresh(r, now)],
            current_time=now,
        )

    # 2. Look up actual_sku in catalog as baseline
    matched_product: Optional[Product] = None
    for p in catalog:
        if p.sku == actual_sku:
            matched_product = p
            break

    if matched_product is None:
        conflicts.append({
            "field": "sku",
            "claimed": actual_sku,
            "actual": "not_found",
        })
        return EvidenceResult(
            conflicts=conflicts,
            sources_checked=sources_checked,
            evidence_details=evidence_details or None,
        )

    # Flatten real product attributes and specs for comparison
    real_specs = dict(matched_product.specs or {})
    top_level_keys = ["brand", "model", "category", "price", "sku"]

    # Helper to get ground truth value: prefers resolved multi-source record if present, else catalog
    def _get_truth_val(field_name: str, fallback_val: Any) -> Any:
        if field_name in resolved_sources:
            return resolved_sources[field_name].value
        return fallback_val

    # Check claimed_product attributes
    for key, claimed_val in claimed_product.items():
        if key == "specs" and isinstance(claimed_val, dict):
            for spec_k, spec_v in claimed_val.items():
                if spec_k in real_specs or spec_k in resolved_sources:
                    actual_v = _get_truth_val(spec_k, real_specs.get(spec_k))
                    if actual_v is not None and not _match_val(spec_v, actual_v, spec_k):
                        conflicts.append({
                            "field": spec_k,
                            "claimed": spec_v,
                            "actual": actual_v,
                        })
        elif key in top_level_keys:
            actual_v = _get_truth_val(key, getattr(matched_product, key, None))
            if actual_v is not None and not _match_val(claimed_val, actual_v, key):
                conflicts.append({
                    "field": key,
                    "claimed": claimed_val,
                    "actual": actual_v,
                })
        elif key in real_specs or key in resolved_sources:
            actual_v = _get_truth_val(key, real_specs.get(key))
            if actual_v is not None and not _match_val(claimed_val, actual_v, key):
                conflicts.append({
                    "field": key,
                    "claimed": claimed_val,
                    "actual": actual_v,
                })

    return EvidenceResult(
        conflicts=conflicts,
        sources_checked=sources_checked,
        evidence_details=evidence_details or None,
    )
