import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from data.schema import Product
from evidence.sources import EvidenceSourceRecord, is_record_fresh, resolve_source_records, get_source_rank


SPEC_CANONICAL_ALIASES = {
    # RAM aliases
    "system_memory_gb": "ram_gb",
    "system_memory": "ram_gb",
    "main_ram": "ram_gb",
    "main_ram_capacity": "ram_gb",
    "ram_size": "ram_gb",
    "memory_gb": "ram_gb",
    "ram": "ram_gb",
    "system_ram": "ram_gb",
    "installed_ram": "ram_gb",
    # Storage aliases
    "storage_drive_size": "storage_gb",
    "disk_capacity_gb": "storage_gb",
    "disk_capacity": "storage_gb",
    "disk_size": "storage_gb",
    "ssd_gb": "storage_gb",
    "hdd_gb": "storage_gb",
    "storage": "storage_gb",
    "capacity_gb": "storage_gb",
    "capacity": "storage_gb",
    "drive_size": "storage_gb",
    # GPU aliases
    "gpu_processor": "gpu",
    "graphics_card": "gpu",
    "gpu_chip": "gpu",
    "video_card": "gpu",
    "graphics": "gpu",
    "gpu_model": "gpu",
    # CPU aliases
    "processor": "cpu",
    "cpu_model": "cpu",
    "cpu_chip": "cpu",
    "processor_type": "cpu",
    "cpu_processor": "cpu",
}


def canonicalize_spec_key(k: str) -> str:
    cleaned = k.lower().strip().replace("-", "_").replace(" ", "_")
    return SPEC_CANONICAL_ALIASES.get(cleaned, cleaned)


def _extract_numeric_spec(val: Any) -> Optional[float]:
    """Extract numeric value from string representations like '128GB', '32 GB', etc."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    if isinstance(val, str):
        match = re.search(r"(\d+(?:\.\d+)?)", val)
        if match:
            return float(match.group(1))
    return None


class EvidenceDetail(BaseModel):
    field: str
    source: str
    observed_value: Any
    retrieved_at: datetime
    is_fresh: bool


class EvidenceResult(BaseModel):
    conflict: bool = False
    conflicts: List[Dict[str, Any]] = []
    unverifiable: bool = False
    discrepancies: List[str] = []
    sources_checked: List[str] = []
    unverifiable_attributes: Optional[List[Dict[str, Any]]] = None
    verification_status: str = "verified" # "verified", "conflict", "unverifiable"
    evidence_details: Optional[List[EvidenceDetail]] = None


def _match_val(claimed_val: Any, actual_val: Any, field_name: str) -> bool:
    """Compare claimed value with actual catalog value."""
    canonical_f = canonicalize_spec_key(field_name)

    if canonical_f == "price" or (
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

    # Numeric spec extraction for ram_gb, storage_gb, etc.
    if canonical_f in ("ram_gb", "storage_gb", "capacity_gb", "read_mbps", "battery_mah", "display_inch"):
        c_num = _extract_numeric_spec(claimed_val)
        a_num = _extract_numeric_spec(actual_val)
        if c_num is not None and a_num is not None:
            return abs(c_num - a_num) < 0.01

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
    Supports multi-source evidence resolution, TTL freshness checks, and unverifiable attribute detection.
    """
    sources_checked: List[str] = ["catalog_spec"]
    conflicts: List[Dict[str, Any]] = []
    unverifiable_attributes: List[Dict[str, Any]] = []
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
            unverifiable_attributes=None,
            verification_status="conflict",
            evidence_details=evidence_details or None,
        )

    # Flatten and canonicalize real product attributes and specs for comparison
    real_specs = dict(matched_product.specs or {})
    canon_real_specs = {canonicalize_spec_key(k): v for k, v in real_specs.items()}
    top_level_keys = ["brand", "model", "category", "price", "sku"]

    # Helper to get ground truth value: prefers resolved multi-source record if present, else catalog
    def _get_truth_val(field_name: str, fallback_val: Any) -> Any:
        canon_f = canonicalize_spec_key(field_name)
        if canon_f in resolved_sources:
            return resolved_sources[canon_f].value
        if field_name in resolved_sources:
            return resolved_sources[field_name].value
        if canon_f in canon_real_specs:
            return canon_real_specs[canon_f]
        return fallback_val

    # Check claimed_product attributes
    for key, claimed_val in claimed_product.items():
        canon_key = canonicalize_spec_key(key)
        if key == "specs" and isinstance(claimed_val, dict):
            for spec_k, spec_v in claimed_val.items():
                canon_spec_k = canonicalize_spec_key(spec_k)
                if canon_spec_k in canon_real_specs or canon_spec_k in resolved_sources or spec_k in real_specs:
                    actual_v = _get_truth_val(canon_spec_k, canon_real_specs.get(canon_spec_k, real_specs.get(spec_k)))
                    if actual_v is not None and not _match_val(spec_v, actual_v, canon_spec_k):
                        conflicts.append({
                            "field": canon_spec_k,
                            "claimed": spec_v,
                            "actual": actual_v,
                        })
                else:
                    unverifiable_attributes.append({
                        "field": spec_k,
                        "claimed": spec_v,
                        "reason": "attribute_not_found_in_catalog_specs",
                    })
        elif key in top_level_keys:
            actual_v = _get_truth_val(key, getattr(matched_product, key, None))
            if actual_v is not None and not _match_val(claimed_val, actual_v, key):
                conflicts.append({
                    "field": key,
                    "claimed": claimed_val,
                    "actual": actual_v,
                })
        elif canon_key in canon_real_specs or canon_key in resolved_sources:
            actual_v = _get_truth_val(canon_key, canon_real_specs.get(canon_key))
            if actual_v is not None and not _match_val(claimed_val, actual_v, canon_key):
                conflicts.append({
                    "field": canon_key,
                    "claimed": claimed_val,
                    "actual": actual_v,
                })
        else:
            unverifiable_attributes.append({
                "field": key,
                "claimed": claimed_val,
                "reason": "attribute_not_found_in_catalog_specs",
            })

    has_conflict = len(conflicts) > 0
    has_unverifiable = len(unverifiable_attributes) > 0
    discrepancies = [
        f"{c['field']} mismatch (claimed '{c.get('claimed')}' vs actual '{c.get('actual')}')"
        for c in conflicts
    ]

    if has_conflict:
        v_status = "conflict"
    elif has_unverifiable:
        v_status = "unverifiable"
    else:
        v_status = "verified"

    return EvidenceResult(
        conflict=has_conflict,
        conflicts=conflicts,
        unverifiable=has_unverifiable,
        discrepancies=discrepancies,
        sources_checked=sources_checked,
        unverifiable_attributes=unverifiable_attributes or None,
        verification_status=v_status,
        evidence_details=evidence_details or None,
    )
