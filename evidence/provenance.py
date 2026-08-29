from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from data.schema import Product
from intent.schema import UserIntent

PROVENANCE_LOG: List[Dict[str, Any]] = []


def log_provenance_event(transaction_id: str, seq: int, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Appends a structured decision provenance event to the log."""
    event = {
        "transaction_id": transaction_id,
        "seq": seq,
        "event_type": event_type,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    PROVENANCE_LOG.append(event)
    return event


def get_provenance_for_transaction(transaction_id: str) -> List[Dict[str, Any]]:
    """Retrieve all provenance events for a given transaction."""
    return [e for e in PROVENANCE_LOG if e["transaction_id"] == transaction_id]


def clear_provenance_log():
    """Clear in-memory provenance log."""
    PROVENANCE_LOG.clear()


def build_provenance_trail(
    transaction_id: str,
    intent: UserIntent,
    catalog: List[Product],
    selected_sku: str,
) -> List[Dict[str, Any]]:
    """
    Synthesizes the observable decision provenance trail for a transaction:
    1. Search query derived from user intent
    2. Candidates found in relevant category
    3. Candidate elimination reasons
    4. Final product selection rationale
    
    All steps derived directly from existing intent and catalog data.
    """
    trail: List[Dict[str, Any]] = []
    seq = 1

    # Find the target category from hard requirements or selected SKU
    selected_product: Optional[Product] = next((p for p in catalog if p.sku == selected_sku), None)
    target_category = intent.hard_requirements.get("category")
    if not target_category and selected_product:
        target_category = selected_product.category

    # 1. Search Event
    search_event = log_provenance_event(
        transaction_id=transaction_id,
        seq=seq,
        event_type="search",
        payload={
            "query": intent.hard_requirements,
            "preferences": intent.soft_preferences,
            "substitution_allowed": intent.substitution_allowed,
        },
    )
    trail.append(search_event)
    seq += 1

    # 2. Candidates Found Event
    candidates = [p for p in catalog if target_category is None or p.category == target_category]
    candidates_event = log_provenance_event(
        transaction_id=transaction_id,
        seq=seq,
        event_type="candidates_found",
        payload={
            "category": target_category or "all",
            "candidate_count": len(candidates),
            "candidate_skus": [p.sku for p in candidates],
        },
    )
    trail.append(candidates_event)
    seq += 1

    # 3. Candidates Eliminated Events
    eliminated_reasons = []
    for cand in candidates:
        if cand.sku == selected_sku:
            continue

        reasons = []
        # Check why cand was eliminated against hard requirements
        for k, v in intent.hard_requirements.items():
            if k in ("max_price", "price_max", "max_amount"):
                if cand.price > float(v):
                    reasons.append(f"price ₹{cand.price:,.2f} exceeds ceiling ₹{float(v):,.2f}")
            elif hasattr(cand, k):
                cand_val = getattr(cand, k)
                if str(cand_val).lower() != str(v).lower():
                    reasons.append(f"{k} '{cand_val}' != requested '{v}'")
            elif cand.specs and k in cand.specs:
                spec_val = cand.specs[k]
                if str(spec_val).lower() != str(v).lower():
                    reasons.append(f"spec {k} '{spec_val}' != requested '{v}'")

        if not reasons:
            reasons.append(f"price ₹{cand.price:,.2f} less optimal or alternative option")

        eliminated_reasons.append({
            "sku": cand.sku,
            "brand": cand.brand,
            "model": cand.model,
            "price": cand.price,
            "reasons": reasons,
        })

    eliminated_event = log_provenance_event(
        transaction_id=transaction_id,
        seq=seq,
        event_type="candidates_eliminated",
        payload={
            "eliminated_count": len(eliminated_reasons),
            "eliminations": eliminated_reasons,
        },
    )
    trail.append(eliminated_event)
    seq += 1

    # 4. Selection Event
    if selected_product:
        selection_reason = (
            f"Selected {selected_product.brand} {selected_product.model} (₹{selected_product.price:,.2f})"
        )
        if intent.substitution_allowed and any(
            str(getattr(selected_product, k, "")).lower() != str(v).lower()
            for k, v in intent.hard_requirements.items() if k in ["model", "specs"]
        ):
            selection_reason += " as closest available substitute within policy"
        else:
            selection_reason += " fulfilling user requirements and mandate policy"

        selected_event = log_provenance_event(
            transaction_id=transaction_id,
            seq=seq,
            event_type="selected",
            payload={
                "sku": selected_product.sku,
                "brand": selected_product.brand,
                "model": selected_product.model,
                "price": selected_product.price,
                "reason": selection_reason,
            },
        )
        trail.append(selected_event)

    return trail
