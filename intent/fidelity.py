from typing import List, Dict, Any
from pydantic import BaseModel

from intent.schema import UserIntent
from data.schema import Product


class IntentFidelityResult(BaseModel):
    hard_match: bool
    soft_score: float
    mismatched_fields: List[str]


def _get_product_attribute(product: Product, key: str) -> Any:
    """Helper to retrieve an attribute from Product fields or product.specs."""
    if hasattr(product, key):
        return getattr(product, key)
    if product.specs and key in product.specs:
        return product.specs[key]
    return None


def _values_match(val1: Any, val2: Any) -> bool:
    """Compare two values with case-insensitivity for strings."""
    if isinstance(val1, str) and isinstance(val2, str):
        return val1.strip().lower() == val2.strip().lower()
    return val1 == val2


def check_intent_fidelity(intent: UserIntent, actual_product: Product) -> IntentFidelityResult:
    """
    Evaluates how closely the actual purchased product matches the user's intent under Pillar 2 (Intent Fidelity).
    
    1. Hard Requirements:
       - Every requirement must match exactly, except price ceilings (max_price) which require actual_product.price <= value.
       - Mismatches are recorded in mismatched_fields, causing hard_match=False.
       
    2. Soft Preferences:
       - Scored only if the preference maps to a recognizable structured attribute in product or specs.
       - Free-text / non-existent fields are ignored from denominator rather than penalizing arbitrarily.
       - soft_score = matched_scoreable / total_scoreable (defaults to 1.0 if total_scoreable == 0).
    """
    mismatched_fields: List[str] = []

    # 1. Evaluate Hard Requirements
    for key, req_val in intent.hard_requirements.items():
        if key in ("max_price", "price_max", "max_amount", "price_ceiling"):
            if actual_product.price > float(req_val):
                mismatched_fields.append(key)
        elif key in ("min_price", "price_min", "min_amount"):
            if actual_product.price < float(req_val):
                mismatched_fields.append(key)
        else:
            actual_val = _get_product_attribute(actual_product, key)
            if actual_val is None:
                mismatched_fields.append(key)
            elif not _values_match(actual_val, req_val):
                mismatched_fields.append(key)

    hard_match = len(mismatched_fields) == 0

    # 2. Evaluate Soft Preferences with Weighted Scoring
    total_weight = 0.0
    matched_weight = 0.0

    for key, pref_item in intent.soft_preferences.items():
        # Handle either raw value or structured {"val": ..., "weight": ...} / WeightedPreference
        if isinstance(pref_item, dict) and "val" in pref_item:
            pref_val = pref_item["val"]
            weight = float(pref_item.get("weight", 1.0))
        elif hasattr(pref_item, "val") and hasattr(pref_item, "weight"):
            pref_val = pref_item.val
            weight = float(pref_item.weight)
        else:
            pref_val = pref_item
            weight = 1.0

        actual_val = _get_product_attribute(actual_product, key)
        if actual_val is not None:
            total_weight += weight
            if _values_match(actual_val, pref_val):
                matched_weight += weight

    if total_weight > 0:
        soft_score = matched_weight / total_weight
    else:
        soft_score = 1.0

    return IntentFidelityResult(
        hard_match=hard_match,
        soft_score=round(soft_score, 4),
        mismatched_fields=mismatched_fields,
    )
