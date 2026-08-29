import pytest
from datetime import datetime, timezone
from data.schema import PurchaseSession, TransactionRequest
from session.manager import (
    create_session,
    get_session,
    list_sessions,
    record_session_transaction,
    get_session_transactions,
    clear_sessions,
)
from intent.schema import UserIntent
from intent.versioning import compute_intent_hash, create_intent_version
from policy.schema import Mandate, TimeWindowRule


@pytest.fixture(autouse=True)
def reset_session_registry():
    clear_sessions()
    yield
    clear_sessions()


def test_session_lifecycle():
    # 1. Create session
    session = create_session(
        intent_id="intent_001",
        agent_id="agent_shopping_01",
        declared_item_count=3,
        declared_total_budget=50000.0,
        session_id="sess_test_123",
    )
    assert session.session_id == "sess_test_123"
    assert session.intent_id == "intent_001"
    assert session.agent_id == "agent_shopping_01"
    assert session.declared_item_count == 3
    assert session.declared_total_budget == 50000.0

    # 2. Get session
    retrieved = get_session("sess_test_123")
    assert retrieved is not None
    assert retrieved.session_id == "sess_test_123"

    # 3. List sessions
    all_sessions = list_sessions(agent_id="agent_shopping_01")
    assert len(all_sessions) == 1

    # 4. Associate transactions
    record_session_transaction("sess_test_123", "tx_001")
    record_session_transaction("sess_test_123", "tx_002")
    tx_ids = get_session_transactions("sess_test_123")
    assert tx_ids == ["tx_001", "tx_002"]


def test_transaction_request_backward_compatibility():
    tx = TransactionRequest(
        id="tx_test_compat",
        agent_id="agent_shopping_01",
        mandate_id="mandate_shop_01",
        user_intent_id="intent_001",
        claimed_product={"brand": "Sony", "model": "WH-1000XM5"},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=29990.0,
        category="electronics",
        merchant="Sony Center",
        timestamp=datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc),
        scenario_type="legitimate_unusual",
        expected_decision="ALLOW",
    )
    # Confirm default backward-compatible fields
    assert tx.session_id is None
    assert tx.intent_version == 1

    # With optional session_id and intent_version
    tx_with_session = TransactionRequest(
        id="tx_test_session",
        agent_id="agent_shopping_01",
        mandate_id="mandate_shop_01",
        user_intent_id="intent_001",
        claimed_product={"brand": "Sony", "model": "WH-1000XM5"},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=29990.0,
        category="electronics",
        merchant="Sony Center",
        timestamp=datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc),
        scenario_type="legitimate_unusual",
        expected_decision="ALLOW",
        session_id="sess_test_123",
        intent_version=2,
    )
    assert tx_with_session.session_id == "sess_test_123"
    assert tx_with_session.intent_version == 2


def test_intent_versioning_and_hashing():
    intent_v1 = UserIntent(
        id="intent_001",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5"},
        soft_preferences={"color": "black"},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc),
    )
    # Automatic hash computation
    assert intent_v1.intent_version == 1
    assert intent_v1.parent_intent_id is None
    assert intent_v1.intent_hash is not None
    expected_hash = compute_intent_hash(
        intent_v1.hard_requirements,
        intent_v1.soft_preferences,
        intent_v1.substitution_allowed,
    )
    assert intent_v1.intent_hash == expected_hash

    # Create version 2 with modified soft preferences
    intent_v2 = create_intent_version(
        base_intent=intent_v1,
        updated_soft_preferences={"color": "silver"},
        substitution_allowed=True,
    )
    assert intent_v2.id == "intent_001_v2"
    assert intent_v2.intent_version == 2
    assert intent_v2.parent_intent_id == "intent_001"
    assert intent_v2.soft_preferences == {"color": "silver"}
    assert intent_v2.substitution_allowed is True
    assert intent_v2.intent_hash != intent_v1.intent_hash


def test_mandate_multi_window_and_period_caps_scaffolding():
    rule1 = TimeWindowRule(days_of_week=["monday", "tuesday", "wednesday", "thursday", "friday"], start="09:00", end="18:00")
    rule2 = TimeWindowRule(days_of_week=["saturday", "sunday"], start="10:00", end="16:00")

    mandate = Mandate(
        id="mandate_scaffold_01",
        agent_id="agent_shopping_01",
        per_transaction_cap=40000.0,
        categories=["electronics"],
        merchants=["Amazon", "Sony Center"],
        time_window_start="08:00",
        time_window_end="22:00",
        issued_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=2592000,
        time_windows=[rule1, rule2],
        period_caps={"daily": 60000.0, "monthly": 250000.0},
    )

    assert mandate.time_window_start == "08:00"
    assert len(mandate.time_windows) == 2
    assert mandate.period_caps["daily"] == 60000.0
    assert mandate.period_caps["monthly"] == 250000.0
