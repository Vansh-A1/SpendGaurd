"""
SpendGuard Trap Catalog Mock Server
Serves realistic mock product listings embedded with adversarial trap archetypes.
Carries X-Simulation: true header to ensure safe isolation from live production.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Response, HTTPException, Query

router = APIRouter(prefix="/simulator", tags=["Simulator Catalog"])
CATALOG_PATH = Path(__file__).resolve().parent / "trap_catalog.json"

_CACHED_TRAP_CATALOG: Optional[List[Dict[str, Any]]] = None


def get_trap_catalog() -> List[Dict[str, Any]]:
    global _CACHED_TRAP_CATALOG
    if _CACHED_TRAP_CATALOG is None:
        if CATALOG_PATH.exists():
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                _CACHED_TRAP_CATALOG = json.load(f)
        else:
            _CACHED_TRAP_CATALOG = []
    return _CACHED_TRAP_CATALOG


@router.get("/products")
def search_products(
    response: Response,
    q: Optional[str] = Query(None, description="Search keyword"),
    category: Optional[str] = Query(None, description="Category filter"),
    max_price: Optional[float] = Query(None, description="Maximum price ceiling"),
    trap_type: Optional[str] = Query(None, description="Filter by trap type"),
):
    response.headers["X-Simulation"] = "true"
    products = get_trap_catalog()
    results = []

    for p in products:
        if category and p.get("category", "").lower() != category.lower():
            continue
        if max_price is not None and float(p.get("price", 0)) > max_price:
            continue
        if trap_type and p.get("trap_type", "").lower() != trap_type.lower():
            continue
        if q:
            keyword = q.lower()
            name_match = keyword in p.get("name", "").lower()
            brand_match = keyword in p.get("brand", "").lower()
            model_match = keyword in p.get("model", "").lower()
            claims_match = keyword in json.dumps(p.get("listing_claims", {})).lower()
            if not (name_match or brand_match or model_match or claims_match):
                continue
        results.append({
            "sku": p["sku"],
            "name": p["name"],
            "brand": p["brand"],
            "model": p["model"],
            "category": p["category"],
            "price": p["price"],
            "merchant": p["merchant"],
            "trap_type": p["trap_type"],
            "listing_claims": p["listing_claims"],
        })

    return {
        "simulation": True,
        "count": len(results),
        "products": results,
    }


@router.get("/products/{sku}")
def get_product_detail(sku: str, response: Response):
    response.headers["X-Simulation"] = "true"
    products = get_trap_catalog()
    product = next((p for p in products if p["sku"].upper() == sku.upper()), None)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product with SKU '{sku}' not found in simulation catalog.")
    return {
        "simulation": True,
        "product": product,
    }
