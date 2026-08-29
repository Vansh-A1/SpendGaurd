from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import math

from data.schema import Product


class EvidenceResult(BaseModel):
    conflicts: List[Dict[str, Any]]
    sources_checked: List[str]


def _match_val(claimed_val: Any, actual_val: Any, field_name: str) -> bool:
    """Compare claimed value with actual catalog value."""
    if field_name == "price" or (isinstance(claimed_val, (int, float)) and isinstance(actual_val, (int, float)) and not isinstance(claimed_val, bool) and not isinstance(actual_val, bool)):
        # Price tolerance check: within 1%
        c_num = float(claimed_val)
        a_num = float(actual_val)
        if a_num == 0:
            return c_num == 0
        return abs(c_num - a_num) / a_num <= 0.01

    if isinstance(claimed_val, str) and isinstance(actual_val, str):
        return claimed_val.strip().lower() == actual_val.strip().lower()

    return claimed_val == actual_val


def check_evidence(claimed_product: Dict[str, Any], actual_sku: str, catalog: List[Product]) -> EvidenceResult:
    """
    Verifies agent claims about a product against trusted merchant/catalog ground truth.
    
    1. Looks up actual_sku in catalog.
    2. Compares claimed attributes and claimed specs against real catalog product.
    3. Records any mismatch as a conflict {field, claimed, actual}.
    4. If actual_sku does not exist in catalog, flags {field: "sku", claimed: actual_sku, actual: "not_found"}.
    """
    sources_checked = ["catalog_spec"]
    conflicts: List[Dict[str, Any]] = []

    # Look up actual_sku in catalog
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
        return EvidenceResult(conflicts=conflicts, sources_checked=sources_checked)

    # Flatten real product attributes and specs for comparison
    real_specs = dict(matched_product.specs or {})
    top_level_keys = ["brand", "model", "category", "price", "sku"]

    # Check claimed_product attributes
    for key, claimed_val in claimed_product.items():
        if key == "specs" and isinstance(claimed_val, dict):
            # Nested specs dictionary
            for spec_k, spec_v in claimed_val.items():
                if spec_k in real_specs:
                    actual_v = real_specs[spec_k]
                    if not _match_val(spec_v, actual_v, spec_k):
                        conflicts.append({
                            "field": spec_k,
                            "claimed": spec_v,
                            "actual": actual_v,
                        })
        elif key in top_level_keys:
            actual_v = getattr(matched_product, key)
            if not _match_val(claimed_val, actual_v, key):
                conflicts.append({
                    "field": key,
                    "claimed": claimed_val,
                    "actual": actual_v,
                })
        elif key in real_specs:
            actual_v = real_specs[key]
            if not _match_val(claimed_val, actual_v, key):
                conflicts.append({
                    "field": key,
                    "claimed": claimed_val,
                    "actual": actual_v,
                })

    return EvidenceResult(
        conflicts=conflicts,
        sources_checked=sources_checked,
    )
