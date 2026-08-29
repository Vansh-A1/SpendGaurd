import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.schema import Agent
from policy.schema import Mandate

AGENTS = [
    Agent(
        id="agent_shopping_01",
        type="shopping",
        name="Primary Consumer Shopping Agent",
        created_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    ),
    Agent(
        id="agent_travel_01",
        type="travel",
        name="Corporate Travel Booking Agent",
        created_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    ),
    Agent(
        id="agent_grocery_01",
        type="grocery",
        name="Household Grocery Procurement Agent",
        created_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    ),
    Agent(
        id="agent_software_01",
        type="software",
        name="DevOps & Engineering SaaS License Agent",
        created_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
    ),
    Agent(
        id="agent_shopping_cold",
        type="shopping",
        name="Cold-Start Guest Shopping Agent",
        created_at=datetime(2026, 8, 28, 14, 30, 0, tzinfo=timezone.utc),
    ),
]

MANDATES = [
    Mandate(
        id="mandate_shop_01",
        agent_id="agent_shopping_01",
        per_transaction_cap=40000.0,
        categories=["electronics"],
        merchants=["Amazon", "Croma", "Sony Center", "Dell Official Store", "Apple Store", "Reliance Digital"],
        time_window_start="08:00",
        time_window_end="22:00",
        issued_at=datetime(2026, 8, 1, 10, 30, 0, tzinfo=timezone.utc),
        ttl_seconds=30 * 24 * 3600,  # 30 days
    ),
    Mandate(
        id="mandate_trav_01",
        agent_id="agent_travel_01",
        per_transaction_cap=60000.0,
        categories=["travel"],
        merchants=["IndiGo", "Air India", "Taj Hotels", "Marriott", "Uber", "MakeMyTrip", "Zostel"],
        time_window_start="06:00",
        time_window_end="23:59",
        issued_at=datetime(2026, 8, 1, 10, 30, 0, tzinfo=timezone.utc),
        ttl_seconds=30 * 24 * 3600,
    ),
    Mandate(
        id="mandate_groc_01",
        agent_id="agent_grocery_01",
        per_transaction_cap=5000.0,
        categories=["groceries"],
        merchants=["Blinkit", "Instamart", "Zepto", "BigBasket", "Amazon Fresh"],
        time_window_start="06:00",
        time_window_end="23:00",
        issued_at=datetime(2026, 8, 1, 10, 30, 0, tzinfo=timezone.utc),
        ttl_seconds=30 * 24 * 3600,
    ),
    Mandate(
        id="mandate_soft_01",
        agent_id="agent_software_01",
        per_transaction_cap=50000.0,
        categories=["software"],
        merchants=["GitHub", "JetBrains", "Notion", "OpenAI", "Adobe", "1Password", "AWS"],
        time_window_start="00:00",
        time_window_end="23:59",
        issued_at=datetime(2026, 8, 1, 10, 30, 0, tzinfo=timezone.utc),
        ttl_seconds=30 * 24 * 3600,
    ),
    Mandate(
        id="mandate_shop_cold",
        agent_id="agent_shopping_cold",
        per_transaction_cap=35000.0,
        categories=["electronics", "software"],
        merchants=["Amazon", "Flipkart", "Apple Store", "GitHub", "Notion"],
        time_window_start="08:00",
        time_window_end="22:00",
        issued_at=datetime(2026, 8, 28, 15, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=14 * 24 * 3600,  # 14 days
    ),
]


def generate_and_save():
    data_dir = Path(__file__).resolve().parent
    agents_file = data_dir / "agents.json"
    mandates_file = data_dir / "mandates.json"

    # Serialize Agents
    agents_data = [agent.model_dump(mode="json") for agent in AGENTS]
    with open(agents_file, "w", encoding="utf-8") as f:
        json.dump(agents_data, f, indent=2)

    # Serialize Mandates
    mandates_data = [mandate.model_dump(mode="json") for mandate in MANDATES]
    with open(mandates_file, "w", encoding="utf-8") as f:
        json.dump(mandates_data, f, indent=2)

    print(f"Saved {len(AGENTS)} agents to {agents_file}")
    print(f"Saved {len(MANDATES)} mandates to {mandates_file}")


if __name__ == "__main__":
    generate_and_save()
