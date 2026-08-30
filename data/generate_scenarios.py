import csv
import json
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.schema import TransactionRequest
from intent.schema import UserIntent
from policy.schema import Mandate
from data.catalog import get_catalog, get_product_by_sku


def load_agents_and_mandates():
    data_dir = Path(__file__).resolve().parent
    with open(data_dir / "agents.json", "r", encoding="utf-8") as f:
        agents = json.load(f)
    with open(data_dir / "mandates.json", "r", encoding="utf-8") as f:
        mandates_raw = json.load(f)

    mandates = {
        m["agent_id"]: Mandate(
            id=m["id"],
            agent_id=m["agent_id"],
            per_transaction_cap=m["per_transaction_cap"],
            categories=m["categories"],
            merchants=m["merchants"],
            time_window_start=m["time_window_start"],
            time_window_end=m["time_window_end"],
            issued_at=datetime.fromisoformat(m["issued_at"]),
            ttl_seconds=m["ttl_seconds"],
        )
        for m in mandates_raw
    }
    return agents, mandates


def generate_scenarios():
    agents, mandates = load_agents_and_mandates()
    catalog = get_catalog()
    cat_by_sku = {p.sku: p for p in catalog}

    requests: List[TransactionRequest] = []
    intents: List[UserIntent] = []

    req_idx = 1
    intent_idx = 1

    base_time = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Helper to add transaction and intent
    def add_tx_and_intent(
        agent_id: str,
        actual_sku: str,
        claimed_product: dict,
        amount: float,
        category: str,
        merchant: str,
        timestamp: datetime,
        scenario_type: str,
        expected_decision: str,
        hard_reqs: dict = None,
        soft_prefs: dict = None,
        sub_allowed: bool = False,
        session_id: str = None,
        intent_version: int = 1,
    ):
        nonlocal req_idx, intent_idx
        mandate = mandates[agent_id]
        
        intent_id = f"intent_{intent_idx:04d}"
        intent_idx += 1
        
        user_intent = UserIntent(
            id=intent_id,
            agent_id=agent_id,
            hard_requirements=hard_reqs or {},
            soft_preferences=soft_prefs or {},
            substitution_allowed=sub_allowed,
            created_at=timestamp - timedelta(minutes=15),
            intent_version=intent_version,
        )
        intents.append(user_intent)

        tx_req = TransactionRequest(
            id=f"tx_{req_idx:04d}",
            agent_id=agent_id,
            mandate_id=mandate.id,
            user_intent_id=intent_id,
            claimed_product=claimed_product,
            actual_sku=actual_sku,
            amount=amount,
            category=category,
            merchant=merchant,
            timestamp=timestamp,
            scenario_type=scenario_type,
            expected_decision=expected_decision,
            session_id=session_id,
            intent_version=intent_version,
        )

        if scenario_type == "legitimate_unusual":
            from policy.authorization import check_authorization
            from intent.fidelity import check_intent_fidelity
            auth_val = check_authorization(tx_req, mandate)
            if not auth_val.passed or auth_val.is_stale:
                raise ValueError(f"Generation error: {tx_req.id} marked legitimate_unusual failed auth ({auth_val.failed_checks})")
            prod_val = cat_by_sku[actual_sku]
            fid_val = check_intent_fidelity(user_intent, prod_val)
            if not fid_val.hard_match:
                raise ValueError(f"Generation error: {tx_req.id} marked legitimate_unusual failed hard match ({fid_val.mismatched_fields})")

        requests.append(tx_req)
        req_idx += 1

    # =========================================================================
    # 1. BUDGET VIOLATION (15 rows) -> BLOCK
    # Amount exceeds mandate.per_transaction_cap
    # =========================================================================
    budget_cases = [
        # agent_shopping_01 (cap 40,000)
        ("agent_shopping_01", "ELEC-APPLE-MACBOOKAIR-M3", 114900.0, "Amazon"),
        ("agent_shopping_01", "ELEC-SAMS-S24U-512", 129999.0, "Croma"),
        ("agent_shopping_01", "ELEC-DELL-G15-4060", 98990.0, "Dell Official Store"),
        ("agent_shopping_01", "ELEC-DELL-G15-3050", 74990.0, "Dell Official Store"),
        ("agent_shopping_01", "ELEC-APPLE-MACBOOKAIR-M3", 114900.0, "Reliance Digital"),
        # agent_grocery_01 (cap 5,000)
        ("agent_grocery_01", "GROC-ORGANIC-ALMONDS-1KG", 9490.0, "BigBasket"),  # 10kg
        ("agent_grocery_01", "GROC-DAAWAT-BIR-5KG", 5700.0, "Blinkit"),  # 6 packs
        ("agent_grocery_01", "GROC-FERRERO-ROCHER-24PK", 6570.0, "Instamart"),  # 6 packs
        ("agent_grocery_01", "GROC-FORTUNE-SUN-5L", 5800.0, "Zepto"),  # 8 jars
        # agent_travel_01 (cap 60,000)
        ("agent_travel_01", "TRAV-TAJ-MUMBAI-DLX", 67500.0, "Taj Hotels"),  # 3 nights
        ("agent_travel_01", "TRAV-MARRIOTT-BLR-EXEC", 67200.0, "Marriott"),  # 4 nights
        ("agent_travel_01", "TRAV-AIRINDIA-DEL-LHR-ECON", 96000.0, "MakeMyTrip"),  # 2 tickets
        # agent_shopping_cold (cap 35,000)
        ("agent_shopping_cold", "SOFT-ADOBE-CC-ALLAPPS-1YR", 47800.0, "Amazon"),
        ("agent_shopping_cold", "ELEC-DELL-G15-3050", 74990.0, "Flipkart"),
        ("agent_shopping_cold", "ELEC-APPLE-MACBOOKAIR-M3", 114900.0, "Apple Store"),
    ]

    for i, (ag_id, sku, amt, merch) in enumerate(budget_cases):
        prod = cat_by_sku[sku]
        add_tx_and_intent(
            agent_id=ag_id,
            actual_sku=prod.sku,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            amount=amt,
            category=prod.category,
            merchant=merch,
            timestamp=base_time + timedelta(minutes=i * 25),
            scenario_type="budget_violation",
            expected_decision="BLOCK",
            hard_reqs={"brand": prod.brand, "category": prod.category, "max_price": amt + 1000},
            soft_prefs={"color": prod.specs.get("color", "standard")},
            sub_allowed=False,
        )

    # =========================================================================
    # 2. WRONG PRODUCT (15 rows) -> BLOCK
    # Amount & category within mandate, but violates hard requirement in UserIntent
    # =========================================================================
    wrong_cases = [
        # Requested Sony WH-1000XM5, bought cheap headphone or kindle
        ("agent_shopping_01", "ELEC-SONY-WHCH520-BLK", 4490.0, "Amazon", {"brand": "Sony", "model": "WH-1000XM5"}),
        ("agent_shopping_01", "ELEC-KINDLE-PW-16GB", 14999.0, "Amazon", {"brand": "Apple", "model": "AirPods Pro (2nd Gen)"}),
        ("agent_shopping_01", "ELEC-BOSE-QC45-BLK", 26900.0, "Croma", {"brand": "Sony", "model": "WH-1000XM5"}),
        ("agent_shopping_01", "ELEC-APPLE-AIRPODSPRO2", 24900.0, "Apple Store", {"brand": "Bose", "model": "QuietComfort 45"}),
        ("agent_shopping_01", "ELEC-SONY-WHCH720N-BLK", 9990.0, "Sony Center", {"brand": "Apple", "category": "electronics"}),
        # Travel: Requested Air India flight, booked hotel or rental
        ("agent_travel_01", "TRAV-UBER-RENTAL-8HR", 2400.0, "Uber", {"brand": "IndiGo", "model": "Flight DEL-BLR 6E-2035"}),
        ("agent_travel_01", "TRAV-ZOSTEL-GOA-PVT", 3200.0, "Zostel", {"brand": "Taj Hotels", "model": "The Taj Mahal Palace - Deluxe Room"}),
        ("agent_travel_01", "TRAV-SAMSONITE-EVOA-55", 18900.0, "MakeMyTrip", {"brand": "Air India", "route": "DEL-LHR"}),
        ("agent_travel_01", "TRAV-INDIGO-DEL-BLR-ECON", 5400.0, "IndiGo", {"brand": "Marriott", "city": "Bengaluru"}),
        # Groceries: Requested Basmati Rice, bought Sunflower Oil
        ("agent_grocery_01", "GROC-FORTUNE-SUN-5L", 725.0, "Blinkit", {"brand": "Daawat", "model": "Ultima Extra Long Basmati Rice 5kg"}),
        ("agent_grocery_01", "GROC-AMUL-GOLD-1L-PK6", 396.0, "Instamart", {"brand": "Nescafe", "model": "Gold Blend Instant Coffee 200g"}),
        ("agent_grocery_01", "GROC-TATA-TEA-GOLD-1KG", 520.0, "Zepto", {"brand": "Ferrero Rocher"}),
        # Software: Requested Copilot, bought 1Password
        ("agent_software_01", "SOFT-1PASSWORD-INDIVIDUAL-1YR", 3200.0, "1Password", {"brand": "GitHub", "model": "GitHub Copilot Individual (1 Year)"}),
        ("agent_software_01", "SOFT-NOTION-PLUS-1YR", 9600.0, "Notion", {"brand": "OpenAI", "model": "ChatGPT Plus Subscription (1 Month)"}),
        ("agent_software_01", "SOFT-OPENAI-CHATGPT-PLUS-1MO", 1999.0, "OpenAI", {"brand": "JetBrains", "model": "All Products Pack (1 Year)"}),
    ]

    for i, (ag_id, sku, amt, merch, hard_req) in enumerate(wrong_cases):
        prod = cat_by_sku[sku]
        add_tx_and_intent(
            agent_id=ag_id,
            actual_sku=prod.sku,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            amount=amt,
            category=prod.category,
            merchant=merch,
            timestamp=base_time + timedelta(minutes=i * 20 + 2),
            scenario_type="wrong_product",
            expected_decision="BLOCK",
            hard_reqs=hard_req,
            soft_prefs={"color": "black"},
            sub_allowed=False,
        )

    # =========================================================================
    # 3. SUBSTITUTION (15 rows) -> VERIFY
    # Near-duplicate SKU, close but not exact match; substitution allowed
    # =========================================================================
    sub_cases = [
        # Requested Sony WH-CH720N (ANC), bought WH-CH520 (no ANC)
        ("agent_shopping_01", "ELEC-SONY-WHCH520-BLK", 4490.0, "Amazon", {"brand": "Sony", "category": "electronics"}, {"model": "WH-CH720N", "anc": True}),
        ("agent_shopping_01", "ELEC-SONY-WHCH520-BLK", 4490.0, "Sony Center", {"brand": "Sony", "category": "electronics"}, {"model": "WH-CH720N", "anc": True}),
        ("agent_shopping_01", "ELEC-SONY-WHCH720N-BLK", 9990.0, "Croma", {"brand": "Sony", "category": "electronics"}, {"model": "WH-CH520", "anc": False}),
        # Requested Sony WH-1000XM5, substituted with Bose QC45
        ("agent_shopping_01", "ELEC-BOSE-QC45-BLK", 26900.0, "Amazon", {"category": "electronics"}, {"brand": "Sony", "model": "WH-1000XM5", "anc": True}),
        ("agent_shopping_01", "ELEC-SONY-WH1000XM5-BLK", 29990.0, "Sony Center", {"category": "electronics"}, {"brand": "Bose", "model": "QuietComfort 45", "anc": True}),
        # Requested Dell G15 4060, substituted with Dell G15 3050 (cap-compatible cold shopper or travel)
        ("agent_shopping_cold", "ELEC-SONY-WHCH520-BLK", 4490.0, "Flipkart", {"brand": "Sony", "category": "electronics"}, {"model": "WH-CH720N", "anc": True}),
        ("agent_shopping_cold", "ELEC-BOSE-QC45-BLK", 26900.0, "Amazon", {"category": "electronics"}, {"brand": "Apple", "model": "AirPods Pro (2nd Gen)", "anc": True}),
        # Travel substitutions: Taj Deluxe substituted with Marriott Exec Suite
        ("agent_travel_01", "TRAV-MARRIOTT-BLR-EXEC", 16800.0, "Marriott", {"category": "travel"}, {"brand": "Taj Hotels", "model": "The Taj Mahal Palace - Deluxe Room", "breakfast": True}),
        ("agent_travel_01", "TRAV-INDIGO-DEL-BLR-ECON", 5400.0, "MakeMyTrip", {"category": "travel"}, {"brand": "Air India", "model": "Flight DEL-BLR AI-505", "refundable": True}),
        ("agent_travel_01", "TRAV-ZOSTEL-GOA-PVT", 3200.0, "Zostel", {"category": "travel"}, {"brand": "Taj Hotels", "ac": True}),
        # Groceries substitutions: Nescafe Gold substituted with Tata Tea Gold
        ("agent_grocery_01", "GROC-TATA-TEA-GOLD-1KG", 520.0, "Blinkit", {"category": "groceries"}, {"brand": "Nescafe", "model": "Gold Blend Instant Coffee 200g", "hot_beverage": True}),
        ("agent_grocery_01", "GROC-ORGANIC-ALMONDS-1KG", 949.0, "Instamart", {"category": "groceries"}, {"brand": "Ferrero Rocher", "snack": True}),
        # Software substitutions: GitHub Copilot substituted with JetBrains All Products or ChatGPT Plus
        ("agent_software_01", "SOFT-OPENAI-CHATGPT-PLUS-1MO", 1999.0, "OpenAI", {"category": "software"}, {"brand": "GitHub", "model": "GitHub Copilot Individual (1 Year)", "ai_assist": True}),
        ("agent_software_01", "SOFT-JETBRAINS-ALLPROD-1YR", 24900.0, "JetBrains", {"category": "software"}, {"brand": "GitHub", "model": "GitHub Copilot Individual (1 Year)", "coding": True}),
        ("agent_software_01", "SOFT-1PASSWORD-INDIVIDUAL-1YR", 3200.0, "1Password", {"category": "software"}, {"brand": "Notion", "model": "Notion Plus Plan (1 Year)", "productivity": True}),
    ]

    for i, (ag_id, sku, amt, merch, hard_req, soft_pref) in enumerate(sub_cases):
        prod = cat_by_sku[sku]
        add_tx_and_intent(
            agent_id=ag_id,
            actual_sku=prod.sku,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            amount=amt,
            category=prod.category,
            merchant=merch,
            timestamp=base_time + timedelta(minutes=i * 20 + 4),
            scenario_type="substitution",
            expected_decision="VERIFY",
            hard_reqs=hard_req,
            soft_prefs=soft_pref,
            sub_allowed=True,
        )

    # =========================================================================
    # 4. SPLIT PAYMENT (20 rows: 2 patterns of 10 linked rapid transactions) -> BLOCK
    # 10 linked transactions from the same agent, each individually under cap,
    # rolling sum in a short window exceeds single large transaction
    # =========================================================================
    # Pattern 1: agent_shopping_01 (cap 40,000), 10 x ₹29,990 transactions in 30 mins (Total ₹299,900)
    burst_time_1 = datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc)
    for j in range(10):
        prod = cat_by_sku["ELEC-SONY-WH1000XM5-BLK"]
        add_tx_and_intent(
            agent_id="agent_shopping_01",
            actual_sku=prod.sku,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            amount=29990.0,
            category="electronics",
            merchant="Amazon",
            timestamp=burst_time_1 + timedelta(minutes=j * 3),
            scenario_type="split_payment",
            expected_decision="VERIFY" if j == 0 else "BLOCK",
            hard_reqs={"brand": "Sony", "model": "WH-1000XM5", "category": "electronics"},
            soft_prefs={"color": "black"},
            sub_allowed=False,
            session_id="sess_split_01",
        )

    # Pattern 2: agent_software_01 (cap 50,000), 10 x ₹24,900 transactions in 20 mins (Total ₹249,000)
    burst_time_2 = datetime(2026, 8, 22, 11, 0, 0, tzinfo=timezone.utc)
    for j in range(10):
        prod = cat_by_sku["SOFT-JETBRAINS-ALLPROD-1YR"]
        add_tx_and_intent(
            agent_id="agent_software_01",
            actual_sku=prod.sku,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            amount=24900.0,
            category="software",
            merchant="JetBrains",
            timestamp=burst_time_2 + timedelta(minutes=j * 2),
            scenario_type="split_payment",
            expected_decision="VERIFY" if j == 0 else "BLOCK",
            hard_reqs={"brand": "JetBrains", "model": "All Products Pack (1 Year)", "category": "software"},
            soft_prefs={"billing": "Annual"},
            sub_allowed=False,
            session_id="sess_split_02",
        )

    # =========================================================================
    # 5. EVIDENCE CONFLICT (15 rows) -> BLOCK
    # Claimed product specs contradict actual_sku's real specs in catalog
    # =========================================================================
    conflict_cases = [
        # ELEC-SONY-WH1000XM5-BLK (real: 30mm driver), claimed 50mm driver
        ("agent_shopping_01", "ELEC-SONY-WH1000XM5-BLK", 29990.0, "Sony Center",
         {"sku": "ELEC-SONY-WH1000XM5-BLK", "brand": "Sony", "model": "WH-1000XM5", "specs": {"driver_mm": 50, "anc": True, "battery_hours": 30}},
         {"brand": "Sony", "model": "WH-1000XM5", "driver_mm": 30}),
        # ELEC-SONY-WHCH520-BLK (real: anc=False), claimed anc=True
        ("agent_shopping_01", "ELEC-SONY-WHCH520-BLK", 4490.0, "Amazon",
         {"sku": "ELEC-SONY-WHCH520-BLK", "brand": "Sony", "model": "WH-CH520", "specs": {"anc": True, "battery_hours": 50, "color": "black"}},
         {"brand": "Sony", "model": "WH-CH520", "anc": False}),
        # ELEC-KINDLE-PW-16GB (real: 16GB), claimed 64GB
        ("agent_shopping_01", "ELEC-KINDLE-PW-16GB", 14999.0, "Amazon",
         {"sku": "ELEC-KINDLE-PW-16GB", "brand": "Amazon", "model": "Kindle Paperwhite", "specs": {"storage_gb": 64, "waterproof": True}},
         {"brand": "Amazon", "model": "Kindle Paperwhite", "storage_gb": 16}),
        # ELEC-APPLE-AIRPODSPRO2 (real: H2 chip), claimed H3 chip
        ("agent_shopping_01", "ELEC-APPLE-AIRPODSPRO2", 24900.0, "Apple Store",
         {"sku": "ELEC-APPLE-AIRPODSPRO2", "brand": "Apple", "model": "AirPods Pro (2nd Gen)", "specs": {"chip": "H3 Ultra", "anc": True}},
         {"brand": "Apple", "model": "AirPods Pro (2nd Gen)", "chip": "H2"}),
        # ELEC-BOSE-QC45-BLK (real: 24hr battery), claimed 60hr battery
        ("agent_shopping_01", "ELEC-BOSE-QC45-BLK", 26900.0, "Croma",
         {"sku": "ELEC-BOSE-QC45-BLK", "brand": "Bose", "model": "QuietComfort 45", "specs": {"battery_hours": 60, "anc": True}},
         {"brand": "Bose", "model": "QuietComfort 45", "battery_hours": 24}),
        # Groceries: GROC-DAAWAT-BIR-5KG (real: 5kg), claimed 10kg
        ("agent_grocery_01", "GROC-DAAWAT-BIR-5KG", 950.0, "Blinkit",
         {"sku": "GROC-DAAWAT-BIR-5KG", "brand": "Daawat", "model": "Ultima Extra Long Basmati Rice 10kg", "specs": {"weight_kg": 10}},
         {"brand": "Daawat", "model": "Ultima Extra Long Basmati Rice 5kg", "weight_kg": 5}),
        # GROC-FORTUNE-SUN-5L (real: 5L), claimed 15L
        ("agent_grocery_01", "GROC-FORTUNE-SUN-5L", 725.0, "Instamart",
         {"sku": "GROC-FORTUNE-SUN-5L", "brand": "Fortune", "model": "Sunlite Refined Sunflower Oil", "specs": {"volume_liters": 15}},
         {"brand": "Fortune", "model": "Sunlite Refined Sunflower Oil 5L Jar", "volume_liters": 5}),
        # GROC-AMUL-GOLD-1L-PK6 (real: 6L), claimed 12L
        ("agent_grocery_01", "GROC-AMUL-GOLD-1L-PK6", 396.0, "Zepto",
         {"sku": "GROC-AMUL-GOLD-1L-PK6", "brand": "Amul", "model": "Gold Full Cream Milk", "specs": {"quantity_liters": 12}},
         {"brand": "Amul", "model": "Gold Full Cream Milk 1L (Pack of 6)", "quantity_liters": 6}),
        # GROC-ORGANIC-ALMONDS-1KG (real: 1kg), claimed 5kg
        ("agent_grocery_01", "GROC-ORGANIC-ALMONDS-1KG", 949.0, "BigBasket",
         {"sku": "GROC-ORGANIC-ALMONDS-1KG", "brand": "Nutraj", "model": "Raw Almonds", "specs": {"weight_kg": 5}},
         {"brand": "Nutraj", "model": "California Raw Almonds 1kg", "weight_kg": 1}),
        # Travel: TRAV-INDIGO-DEL-BLR-ECON (real: non-refundable), claimed refundable
        ("agent_travel_01", "TRAV-INDIGO-DEL-BLR-ECON", 5400.0, "IndiGo",
         {"sku": "TRAV-INDIGO-DEL-BLR-ECON", "brand": "IndiGo", "model": "Flight DEL-BLR 6E-2035", "specs": {"refundable": True, "baggage_kg": 35}},
         {"brand": "IndiGo", "model": "Flight DEL-BLR 6E-2035", "refundable": False}),
        # TRAV-TAJ-MUMBAI-DLX (real: Sea View), claimed Presidential Suite
        ("agent_travel_01", "TRAV-TAJ-MUMBAI-DLX", 22500.0, "Taj Hotels",
         {"sku": "TRAV-TAJ-MUMBAI-DLX", "brand": "Taj Hotels", "model": "Presidential Suite", "specs": {"room_type": "Presidential Palace Suite"}},
         {"brand": "Taj Hotels", "model": "The Taj Mahal Palace - Deluxe Room", "room_type": "Deluxe Sea View"}),
        # TRAV-UBER-RENTAL-8HR (real: Sedan), claimed Luxury SUV
        ("agent_travel_01", "TRAV-UBER-RENTAL-8HR", 2400.0, "Uber",
         {"sku": "TRAV-UBER-RENTAL-8HR", "brand": "Uber", "model": "Uber Black XL", "specs": {"car_type": "Luxury SUV 7-Seater"}},
         {"brand": "Uber", "model": "Uber Premier Rental (8hr/80km)", "car_type": "Sedan"}),
        # Software: SOFT-NOTION-PLUS-1YR (real: Plus plan), claimed Enterprise
        ("agent_software_01", "SOFT-NOTION-PLUS-1YR", 9600.0, "Notion",
         {"sku": "SOFT-NOTION-PLUS-1YR", "brand": "Notion", "model": "Notion Enterprise Plan", "specs": {"plan": "Enterprise", "saml_sso": True}},
         {"brand": "Notion", "model": "Notion Plus Plan (1 Year)", "plan": "Plus"}),
        # SOFT-OPENAI-CHATGPT-PLUS-1MO (real: Monthly), claimed Lifetime
        ("agent_software_01", "SOFT-OPENAI-CHATGPT-PLUS-1MO", 1999.0, "OpenAI",
         {"sku": "SOFT-OPENAI-CHATGPT-PLUS-1MO", "brand": "OpenAI", "model": "ChatGPT Lifetime Access", "specs": {"billing": "Lifetime"}},
         {"brand": "OpenAI", "model": "ChatGPT Plus Subscription (1 Month)", "billing": "Monthly"}),
        # Cold shopper: ELEC-SONY-WHCH520-BLK (real: no ANC), claimed ANC
        ("agent_shopping_cold", "ELEC-SONY-WHCH520-BLK", 4490.0, "Amazon",
         {"sku": "ELEC-SONY-WHCH520-BLK", "brand": "Sony", "model": "WH-CH520 ANC", "specs": {"anc": True}},
         {"brand": "Sony", "model": "WH-CH520", "anc": False}),
    ]

    for i, (ag_id, sku, amt, merch, claimed, hard_req) in enumerate(conflict_cases):
        prod = cat_by_sku[sku]
        add_tx_and_intent(
            agent_id=ag_id,
            actual_sku=prod.sku,
            claimed_product=claimed,
            amount=amt,
            category=prod.category,
            merchant=merch,
            timestamp=base_time + timedelta(minutes=i * 20 + 6),
            scenario_type="evidence_conflict",
            expected_decision="BLOCK",
            hard_reqs=hard_req,
            soft_prefs={"color": "black"},
            sub_allowed=False,
        )

    # =========================================================================
    # 6. STALE MANDATE (15 rows) -> VERIFY
    # Timestamp > mandate.issued_at + mandate.ttl_seconds
    # =========================================================================
    stale_cases = [
        ("agent_shopping_01", "ELEC-SONY-WH1000XM5-BLK", 29990.0, "Sony Center"),
        ("agent_shopping_01", "ELEC-SONY-WHCH720N-BLK", 9990.0, "Amazon"),
        ("agent_shopping_01", "ELEC-APPLE-AIRPODSPRO2", 24900.0, "Apple Store"),
        ("agent_shopping_01", "ELEC-BOSE-QC45-BLK", 26900.0, "Croma"),
        ("agent_travel_01", "TRAV-INDIGO-DEL-BLR-ECON", 5400.0, "IndiGo"),
        ("agent_travel_01", "TRAV-MARRIOTT-BLR-EXEC", 16800.0, "Marriott"),
        ("agent_travel_01", "TRAV-UBER-RENTAL-8HR", 2400.0, "Uber"),
        ("agent_grocery_01", "GROC-AMUL-GOLD-1L-PK6", 396.0, "Blinkit"),
        ("agent_grocery_01", "GROC-DAAWAT-BIR-5KG", 950.0, "Instamart"),
        ("agent_grocery_01", "GROC-ORGANIC-ALMONDS-1KG", 949.0, "BigBasket"),
        ("agent_software_01", "SOFT-GITHUB-COPILOT-1YR", 8500.0, "GitHub"),
        ("agent_software_01", "SOFT-JETBRAINS-ALLPROD-1YR", 24900.0, "JetBrains"),
        ("agent_software_01", "SOFT-NOTION-PLUS-1YR", 9600.0, "Notion"),
        ("agent_shopping_cold", "ELEC-SONY-WHCH720N-BLK", 9990.0, "Amazon"),
        ("agent_shopping_cold", "SOFT-GITHUB-COPILOT-1YR", 8500.0, "GitHub"),
    ]

    for i, (ag_id, sku, amt, merch) in enumerate(stale_cases):
        mand = mandates[ag_id]
        prod = cat_by_sku[sku]
        # Timestamp is 45 days after mandate issued_at (well past 30d/14d TTL)
        stale_timestamp = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=i * 20)
        add_tx_and_intent(
            agent_id=ag_id,
            actual_sku=prod.sku,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            amount=amt,
            category=prod.category,
            merchant=merch,
            timestamp=stale_timestamp,
            scenario_type="stale_mandate",
            expected_decision="VERIFY",
            hard_reqs={"brand": prod.brand, "model": prod.model, "category": prod.category},
            soft_prefs={"color": prod.specs.get("color", "standard")},
            sub_allowed=False,
        )

    # =========================================================================
    # 7. LEGITIMATE UNUSUAL (15 rows) -> ALLOW
    # Hard requirements met, evidence clean, amount & category within mandate,
    # novel agent / first transaction in category
    # =========================================================================
    legit_cases = [
        # Cold start shopping agent first electronics transactions
        ("agent_shopping_cold", "ELEC-SONY-WH1000XM5-BLK", 29990.0, "Amazon"),
        ("agent_shopping_cold", "ELEC-APPLE-AIRPODSPRO2", 24900.0, "Apple Store"),
        ("agent_shopping_cold", "ELEC-SONY-WHCH720N-BLK", 9990.0, "Flipkart"),
        ("agent_shopping_cold", "SOFT-GITHUB-COPILOT-1YR", 8500.0, "GitHub"),
        ("agent_shopping_cold", "SOFT-NOTION-PLUS-1YR", 9600.0, "Notion"),
        # Established shopping agent standard valid transactions
        ("agent_shopping_01", "ELEC-SONY-WH1000XM5-BLK", 29990.0, "Sony Center"),
        ("agent_shopping_01", "ELEC-BOSE-QC45-BLK", 26900.0, "Croma"),
        ("agent_shopping_01", "ELEC-KINDLE-PW-16GB", 14999.0, "Amazon"),
        ("agent_shopping_01", "ELEC-SONY-WHCH720N-BLK", 9990.0, "Amazon"),
        # Travel agent valid travel bookings
        ("agent_travel_01", "TRAV-INDIGO-DEL-BLR-ECON", 5400.0, "IndiGo"),
        ("agent_travel_01", "TRAV-AIRINDIA-DEL-LHR-ECON", 48000.0, "Air India"),
        ("agent_travel_01", "TRAV-TAJ-MUMBAI-DLX", 22500.0, "Taj Hotels"),
        # Grocery agent valid grocery buys
        ("agent_grocery_01", "GROC-AMUL-GOLD-1L-PK6", 396.0, "Blinkit"),
        ("agent_grocery_01", "GROC-DAAWAT-BIR-5KG", 950.0, "Instamart"),
        # Software agent valid license buys
        ("agent_software_01", "SOFT-GITHUB-COPILOT-1YR", 8500.0, "GitHub"),
    ]

    for i, (ag_id, sku, amt, merch) in enumerate(legit_cases):
        prod = cat_by_sku[sku]
        add_tx_and_intent(
            agent_id=ag_id,
            actual_sku=prod.sku,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            amount=amt,
            category=prod.category,
            merchant=merch,
            timestamp=base_time + timedelta(days=2 + i // 4, hours=(i % 4) * 3 + 1),
            scenario_type="legitimate_unusual",
            expected_decision="ALLOW",
            hard_reqs={"brand": prod.brand, "model": prod.model, "category": prod.category},
            soft_prefs={"color": prod.specs.get("color", "standard")},
            sub_allowed=False,
        )

    return requests, intents


def generate_expanded_training_data(base_requests: List[TransactionRequest], base_intents: List[UserIntent]):
    """
    Generates diverse split-payment training bursts across:
    - Burst lengths: {3, 5, 8, 12, 20}
    - Amount-to-cap percentages: {30%, 50%, 75%, 95%}
    - Session configurations: with session_id (cumulative tracking) and without session_id (pure velocity)
    - Complementary diverse benign transactions across categories and time windows
    """
    catalog = get_catalog()
    cat_by_sku = {p.sku: p for p in catalog}

    mandates_file = Path(__file__).resolve().parent / "mandates.json"
    with open(mandates_file, "r", encoding="utf-8") as f:
        mandates_data = json.load(f)
    mandates = {m["agent_id"]: Mandate(**m) for m in mandates_data}

    expanded_requests = list(base_requests)
    expanded_intents = list(base_intents)

    req_idx = len(base_requests) + 1
    intent_idx = len(base_intents) + 1

    train_anchor_time = datetime(2026, 8, 24, 8, 0, 0, tzinfo=timezone.utc)

    # Agents and sample SKUs per category
    agent_configs = [
        ("agent_shopping_01", "electronics", "Amazon", "ELEC-SONY-WH1000XM5-BLK"),
        ("agent_software_01", "software", "JetBrains", "SOFT-JETBRAINS-ALLPROD-1YR"),
        ("agent_travel_01", "travel", "Taj Hotels", "TRAV-TAJ-MUMBAI-DLX"),
        ("agent_grocery_01", "groceries", "Blinkit", "GROC-ORGANIC-ALMONDS-1KG"),
    ]

    burst_lengths = [3, 5, 8, 12, 20]
    cap_percentages = [0.30, 0.50, 0.75, 0.95]
    session_options = [True, False]

    pattern_idx = 0
    for burst_len in burst_lengths:
        for cap_pct in cap_percentages:
            for with_session in session_options:
                pattern_idx += 1
                agent_id, category, merchant, sku = agent_configs[pattern_idx % len(agent_configs)]
                mandate = mandates[agent_id]
                prod = cat_by_sku[sku]
                cap = mandate.per_transaction_cap
                amount = round(cap * cap_pct, 2)
                total_declared_budget = round(amount * burst_len, 2)

                burst_time = train_anchor_time + timedelta(days=pattern_idx // 4, hours=(pattern_idx % 4) * 3)

                session_id = None
                if with_session:
                    session_id = f"sess_train_burst_{pattern_idx:03d}"
                    from session.manager import create_session
                    create_session(
                        session_id=session_id,
                        intent_id=f"intent_train_{intent_idx:04d}",
                        agent_id=agent_id,
                        declared_item_count=burst_len,
                        declared_total_budget=total_declared_budget,
                    )

                # Generate rapid burst transactions (spaced 2 minutes apart within 1 hour)
                for step in range(burst_len):
                    intent_id = f"intent_train_{intent_idx:04d}"
                    intent_idx += 1
                    user_intent = UserIntent(
                        id=intent_id,
                        agent_id=agent_id,
                        hard_requirements={"category": category},
                        soft_preferences={},
                        substitution_allowed=False,
                        created_at=burst_time - timedelta(minutes=15),
                    )
                    expanded_intents.append(user_intent)

                    tx_req = TransactionRequest(
                        id=f"tx_train_{req_idx:04d}",
                        agent_id=agent_id,
                        mandate_id=mandate.id,
                        user_intent_id=intent_id,
                        claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
                        actual_sku=prod.sku,
                        amount=amount,
                        category=category,
                        merchant=merchant,
                        timestamp=burst_time + timedelta(minutes=step * 2),
                        scenario_type="split_payment",
                        expected_decision="BLOCK",
                        session_id=session_id,
                    )
                    expanded_requests.append(tx_req)
                    req_idx += 1

    # Also add diverse benign legitimate single transactions across amounts
    benign_anchor_time = datetime(2026, 8, 25, 9, 0, 0, tzinfo=timezone.utc)
    for b_idx in range(80):
        agent_id, category, merchant, sku = agent_configs[b_idx % len(agent_configs)]
        mandate = mandates[agent_id]
        prod = cat_by_sku[sku]
        amt_pct = 0.20 + (b_idx % 8) * 0.10 # 20% to 90% of cap
        amount = round(mandate.per_transaction_cap * amt_pct, 2)
        tx_time = benign_anchor_time + timedelta(hours=b_idx * 4)

        intent_id = f"intent_train_{intent_idx:04d}"
        intent_idx += 1
        user_intent = UserIntent(
            id=intent_id,
            agent_id=agent_id,
            hard_requirements={"brand": prod.brand, "model": prod.model},
            soft_preferences={},
            substitution_allowed=False,
            created_at=tx_time - timedelta(minutes=20),
        )
        expanded_intents.append(user_intent)

        tx_req = TransactionRequest(
            id=f"tx_train_{req_idx:04d}",
            agent_id=agent_id,
            mandate_id=mandate.id,
            user_intent_id=intent_id,
            claimed_product={"sku": prod.sku, "brand": prod.brand, "model": prod.model, "specs": prod.specs},
            actual_sku=prod.sku,
            amount=amount,
            category=category,
            merchant=merchant,
            timestamp=tx_time,
            scenario_type="legitimate_unusual",
            expected_decision="ALLOW",
        )
        expanded_requests.append(tx_req)
        req_idx += 1

    return expanded_requests, expanded_intents


def save_scenarios_and_intents(
    requests: List[TransactionRequest],
    intents: List[UserIntent],
    train_requests: Optional[List[TransactionRequest]] = None,
    train_intents: Optional[List[UserIntent]] = None,
):
    data_dir = Path(__file__).resolve().parent
    csv_file = data_dir / "scenarios.csv"
    train_csv_file = data_dir / "train_scenarios.csv"
    intents_file = data_dir / "intents.json"

    # All intents dictionary (base + training intents)
    all_intents = list(intents)
    if train_intents:
        all_intents.extend([i for i in train_intents if i.id not in {x.id for x in all_intents}])

    intents_dict = {intent.id: intent.model_dump(mode="json") for intent in all_intents}
    with open(intents_file, "w", encoding="utf-8") as f:
        json.dump(intents_dict, f, indent=2)

    fieldnames = [
        "id",
        "agent_id",
        "mandate_id",
        "user_intent_id",
        "claimed_product",
        "actual_sku",
        "amount",
        "category",
        "merchant",
        "timestamp",
        "scenario_type",
        "expected_decision",
        "session_id",
        "intent_version",
    ]

    # Write canonical benchmark 110 scenarios to scenarios.csv
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for req in requests:
            row = req.model_dump(mode="json")
            row["claimed_product"] = json.dumps(row["claimed_product"])
            writer.writerow(row)

    # Write expanded training dataset to train_scenarios.csv
    target_train_reqs = train_requests or requests
    with open(train_csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for req in target_train_reqs:
            row = req.model_dump(mode="json")
            row["claimed_product"] = json.dumps(row["claimed_product"])
            writer.writerow(row)

    print(f"Saved {len(requests)} TransactionRequests to {csv_file}")
    print(f"Saved {len(target_train_reqs)} TransactionRequests to {train_csv_file}")
    print(f"Saved {len(all_intents)} UserIntents to {intents_file}")

    # Summary by scenario type for training set
    from collections import Counter
    counts = Counter(r.scenario_type for r in target_train_reqs)
    print("\nTraining Dataset Breakdown:")
    for st, count in sorted(counts.items()):
        print(f"  - {st:20s}: {count:2d} rows")


if __name__ == "__main__":
    reqs, ints = generate_scenarios()
    train_reqs, train_ints = generate_expanded_training_data(reqs, ints)
    save_scenarios_and_intents(reqs, ints, train_reqs, train_ints)
