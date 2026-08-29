import sys
from pathlib import Path

# Add project root to sys.path if executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from typing import List
from data.schema import Product

CATALOG: List[Product] = [
    # ---------------------------------------------------------
    # Electronics (10 items, including 2 near-duplicate pairs)
    # ---------------------------------------------------------
    # Near-duplicate Pair 1: Sony Headphone variants (ANC vs No ANC)
    Product(
        sku="ELEC-SONY-WHCH720N-BLK",
        brand="Sony",
        model="WH-CH720N",
        category="electronics",
        price=9990.0,
        specs={"anc": True, "battery_hours": 35, "color": "black", "form_factor": "over-ear"},
    ),
    Product(
        sku="ELEC-SONY-WHCH520-BLK",
        brand="Sony",
        model="WH-CH520",
        category="electronics",
        price=4490.0,
        specs={"anc": False, "battery_hours": 50, "color": "black", "form_factor": "on-ear"},
    ),
    # Near-duplicate Pair 2: Dell Gaming Laptop variants (RTX 4060 vs RTX 3050)
    Product(
        sku="ELEC-DELL-G15-4060",
        brand="Dell",
        model="G15 5530 (RTX 4060)",
        category="electronics",
        price=98990.0,
        specs={"gpu": "RTX 4060", "cpu": "Intel Core i7-13650HX", "ram_gb": 16, "storage_gb": 512, "display_inch": 15.6},
    ),
    Product(
        sku="ELEC-DELL-G15-3050",
        brand="Dell",
        model="G15 5530 (RTX 3050)",
        category="electronics",
        price=74990.0,
        specs={"gpu": "RTX 3050", "cpu": "Intel Core i5-13450HX", "ram_gb": 16, "storage_gb": 512, "display_inch": 15.6},
    ),
    # Premium Flagship Headphones
    Product(
        sku="ELEC-SONY-WH1000XM5-BLK",
        brand="Sony",
        model="WH-1000XM5",
        category="electronics",
        price=29990.0,
        specs={"anc": True, "battery_hours": 30, "color": "black", "form_factor": "over-ear", "driver_mm": 30},
    ),
    Product(
        sku="ELEC-BOSE-QC45-BLK",
        brand="Bose",
        model="QuietComfort 45",
        category="electronics",
        price=26900.0,
        specs={"anc": True, "battery_hours": 24, "color": "triple black", "form_factor": "over-ear"},
    ),
    Product(
        sku="ELEC-APPLE-AIRPODSPRO2",
        brand="Apple",
        model="AirPods Pro (2nd Gen)",
        category="electronics",
        price=24900.0,
        specs={"anc": True, "chip": "H2", "charging": "USB-C", "color": "white"},
    ),
    Product(
        sku="ELEC-APPLE-MACBOOKAIR-M3",
        brand="Apple",
        model="MacBook Air 13 M3",
        category="electronics",
        price=114900.0,
        specs={"chip": "Apple M3", "ram_gb": 16, "storage_gb": 512, "color": "midnight"},
    ),
    Product(
        sku="ELEC-SAMS-S24U-512",
        brand="Samsung",
        model="Galaxy S24 Ultra",
        category="electronics",
        price=129999.0,
        specs={"ram_gb": 12, "storage_gb": 512, "color": "titanium black", "display_inch": 6.8},
    ),
    Product(
        sku="ELEC-KINDLE-PW-16GB",
        brand="Amazon",
        model="Kindle Paperwhite",
        category="electronics",
        price=14999.0,
        specs={"storage_gb": 16, "display_inch": 6.8, "waterproof": True, "warm_light": True},
    ),

    # ---------------------------------------------------------
    # Travel (7 items)
    # ---------------------------------------------------------
    Product(
        sku="TRAV-INDIGO-DEL-BLR-ECON",
        brand="IndiGo",
        model="Flight DEL-BLR 6E-2035",
        category="travel",
        price=5400.0,
        specs={"route": "DEL-BLR", "cabin_class": "Economy", "baggage_kg": 15, "refundable": False},
    ),
    Product(
        sku="TRAV-AIRINDIA-DEL-LHR-ECON",
        brand="Air India",
        model="Flight DEL-LHR AI-161",
        category="travel",
        price=48000.0,
        specs={"route": "DEL-LHR", "cabin_class": "Economy", "baggage_kg": 23, "refundable": True},
    ),
    Product(
        sku="TRAV-TAJ-MUMBAI-DLX",
        brand="Taj Hotels",
        model="The Taj Mahal Palace - Deluxe Room",
        category="travel",
        price=22500.0,
        specs={"city": "Mumbai", "room_type": "Deluxe Sea View", "breakfast_included": True, "wifi": True},
    ),
    Product(
        sku="TRAV-MARRIOTT-BLR-EXEC",
        brand="Marriott",
        model="JW Marriott Bengaluru - Executive Suite",
        category="travel",
        price=16800.0,
        specs={"city": "Bengaluru", "room_type": "Executive Suite", "breakfast_included": True, "pool_access": True},
    ),
    Product(
        sku="TRAV-UBER-RENTAL-8HR",
        brand="Uber",
        model="Uber Premier Rental (8hr/80km)",
        category="travel",
        price=2400.0,
        specs={"duration_hours": 8, "included_km": 80, "car_type": "Sedan"},
    ),
    Product(
        sku="TRAV-SAMSONITE-EVOA-55",
        brand="Samsonite",
        model="Evoa Spinner Cabin Luggage 55cm",
        category="travel",
        price=18900.0,
        specs={"size_cm": 55, "type": "hard-sided", "lock": "TSA", "wheels": 4},
    ),
    Product(
        sku="TRAV-ZOSTEL-GOA-PVT",
        brand="Zostel",
        model="Zostel Goa Morjim - Private Room",
        category="travel",
        price=3200.0,
        specs={"city": "Goa", "room_type": "Private Room", "ac": True, "beachfront": True},
    ),

    # ---------------------------------------------------------
    # Groceries (7 items)
    # ---------------------------------------------------------
    Product(
        sku="GROC-AMUL-GOLD-1L-PK6",
        brand="Amul",
        model="Gold Full Cream Milk 1L (Pack of 6)",
        category="groceries",
        price=396.0,
        specs={"quantity_liters": 6, "type": "Full Cream Milk", "shelf_life_days": 180},
    ),
    Product(
        sku="GROC-DAAWAT-BIR-5KG",
        brand="Daawat",
        model="Ultima Extra Long Basmati Rice 5kg",
        category="groceries",
        price=950.0,
        specs={"weight_kg": 5, "grain_type": "Extra Long Basmati", "aged_years": 2},
    ),
    Product(
        sku="GROC-FORTUNE-SUN-5L",
        brand="Fortune",
        model="Sunlite Refined Sunflower Oil 5L Jar",
        category="groceries",
        price=725.0,
        specs={"volume_liters": 5, "oil_type": "Sunflower", "fortified": True},
    ),
    Product(
        sku="GROC-TATA-TEA-GOLD-1KG",
        brand="Tata Tea",
        model="Tata Tea Gold 1kg",
        category="groceries",
        price=520.0,
        specs={"weight_kg": 1, "blend": "Assam & Long Leaf", "caffeine": True},
    ),
    Product(
        sku="GROC-NESCAFE-GOLD-200G",
        brand="Nescafe",
        model="Gold Blend Instant Coffee 200g",
        category="groceries",
        price=895.0,
        specs={"weight_g": 200, "roast": "Medium", "origin": "Arabica & Robusta"},
    ),
    Product(
        sku="GROC-FERRERO-ROCHER-24PK",
        brand="Ferrero Rocher",
        model="Crispy Hazelnut Chocolates (Pack of 24)",
        category="groceries",
        price=1095.0,
        specs={"count": 24, "type": "Hazelnut Chocolate", "imported": True},
    ),
    Product(
        sku="GROC-ORGANIC-ALMONDS-1KG",
        brand="Nutraj",
        model="California Raw Almonds 1kg",
        category="groceries",
        price=949.0,
        specs={"weight_kg": 1, "grade": "California Jumbo", "organic": True},
    ),

    # ---------------------------------------------------------
    # Software (6 items)
    # ---------------------------------------------------------
    Product(
        sku="SOFT-GITHUB-COPILOT-1YR",
        brand="GitHub",
        model="GitHub Copilot Individual (1 Year)",
        category="software",
        price=8500.0,
        specs={"plan": "Individual", "billing": "Annual", "ai_model": "GPT-4o/Claude-3.5"},
    ),
    Product(
        sku="SOFT-JETBRAINS-ALLPROD-1YR",
        brand="JetBrains",
        model="All Products Pack (1 Year)",
        category="software",
        price=24900.0,
        specs={"plan": "Individual", "ide_count": 16, "billing": "Annual"},
    ),
    Product(
        sku="SOFT-NOTION-PLUS-1YR",
        brand="Notion",
        model="Notion Plus Plan (1 Year)",
        category="software",
        price=9600.0,
        specs={"plan": "Plus", "unlimited_blocks": True, "billing": "Annual"},
    ),
    Product(
        sku="SOFT-OPENAI-CHATGPT-PLUS-1MO",
        brand="OpenAI",
        model="ChatGPT Plus Subscription (1 Month)",
        category="software",
        price=1999.0,
        specs={"plan": "Plus", "access_gpt4": True, "billing": "Monthly"},
    ),
    Product(
        sku="SOFT-ADOBE-CC-ALLAPPS-1YR",
        brand="Adobe",
        model="Creative Cloud All Apps (1 Year)",
        category="software",
        price=47800.0,
        specs={"plan": "All Apps", "cloud_storage_tb": 1, "billing": "Annual"},
    ),
    Product(
        sku="SOFT-1PASSWORD-INDIVIDUAL-1YR",
        brand="1Password",
        model="1Password Individual (1 Year)",
        category="software",
        price=3200.0,
        specs={"plan": "Individual", "unlimited_passwords": True, "vaults": 1, "billing": "Annual"},
    ),
]


def get_catalog() -> List[Product]:
    """Return the synthetic product catalog."""
    return CATALOG


def get_product_by_sku(sku: str) -> Product:
    """Lookup product by exact SKU."""
    for prod in CATALOG:
        if prod.sku == sku:
            return prod
    raise KeyError(f"Product SKU {sku} not found in catalog")


if __name__ == "__main__":
    products = get_catalog()
    print(f"Total Products in Catalog: {len(products)}")
    print(f"Categories: {sorted(list(set(p.category for p in products)))}\n")
    
    print("=== Near-Duplicate SKU Pairs in Electronics ===")
    print("Pair 1 (Headphones: ANC vs Non-ANC):")
    p1_a = get_product_by_sku("ELEC-SONY-WHCH720N-BLK")
    p1_b = get_product_by_sku("ELEC-SONY-WHCH520-BLK")
    print(f"  SKU A: {p1_a.sku} | {p1_a.brand} {p1_a.model} | ₹{p1_a.price} | Specs: {p1_a.specs}")
    print(f"  SKU B: {p1_b.sku} | {p1_b.brand} {p1_b.model} | ₹{p1_b.price} | Specs: {p1_b.specs}")

    print("\nPair 2 (Laptops: RTX 4060 vs RTX 3050):")
    p2_a = get_product_by_sku("ELEC-DELL-G15-4060")
    p2_b = get_product_by_sku("ELEC-DELL-G15-3050")
    print(f"  SKU A: {p2_a.sku} | {p2_a.brand} {p2_a.model} | ₹{p2_a.price} | Specs: {p2_a.specs}")
    print(f"  SKU B: {p2_b.sku} | {p2_b.brand} {p2_b.model} | ₹{p2_b.price} | Specs: {p2_b.specs}")

    print("\n=== Full Catalog List ===")
    for i, p in enumerate(products, 1):
        print(f"{i:02d}. [{p.category.upper():11s}] {p.sku:28s} | {p.brand} - {p.model} | ₹{p.price:,.2f}")
