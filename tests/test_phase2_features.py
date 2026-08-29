import pytest
from datetime import datetime, timezone, timedelta
from data.schema import TransactionRequest, Product, PurchaseSession
from policy.schema import Mandate, TimeWindowRule
from policy.authorization import check_authorization
from intent.schema import UserIntent, WeightedPreference
from intent.fidelity import check_intent_fidelity
from intent.drift import check_goal_drift
from evidence.sources import EvidenceSourceRecord
from evidence.check import check_evidence
from evidence.provenance import (
    build_provenance_trail,
    verify_provenance_chain,
    log_provenance_event,
    clear_provenance_log,
)
from data.catalog import get_catalog


@pytest.fixture(autouse=True)
def clean_provenance():
    clear_provenance_log()
    yield
    clear_provenance_log()


# -----------------------------------------------------------------------------
# TASK 5 TESTS: Multi-Window & Cumulative Period Caps
# -----------------------------------------------------------------------------
def test_multi_window_recurring_rules():
    # Mandate allows Monday-Friday 09:00-17:00 and Saturday 10:00-14:00
    rule_weekday = TimeWindowRule(days_of_week=["monday", "tuesday", "wednesday", "thursday", "friday"], start="09:00", end="17:00")
    rule_saturday = TimeWindowRule(days_of_week=["saturday"], start="10:00", end="14:00")

    mandate = Mandate(
        id="mandate_multi_win",
        agent_id="agent_shopping_01",
        per_transaction_cap=50000.0,
        categories=["electronics"],
        merchants=["Amazon"],
        time_window_start="00:00",
        time_window_end="23:59",
        issued_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=3600000,
        time_windows=[rule_weekday, rule_saturday],
    )

    # 1. Monday at 11:00 UTC (valid)
    tx_valid = TransactionRequest(
        id="tx_win_1",
        agent_id="agent_shopping_01",
        mandate_id="mandate_multi_win",
        user_intent_id="intent_001",
        claimed_product={"brand": "Sony"},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=29990.0,
        category="electronics",
        merchant="Amazon",
        timestamp=datetime(2026, 8, 17, 11, 0, 0, tzinfo=timezone.utc), # Monday
        scenario_type="legitimate_unusual",
        expected_decision="ALLOW",
    )
    res_valid = check_authorization(tx_valid, mandate)
    assert res_valid.passed is True

    # 2. Monday at 20:00 UTC (outside hours)
    tx_invalid_time = tx_valid.model_copy(update={"timestamp": datetime(2026, 8, 17, 20, 0, 0, tzinfo=timezone.utc)})
    res_inv_time = check_authorization(tx_invalid_time, mandate)
    assert res_inv_time.passed is False
    assert "outside_time_window" in res_inv_time.failed_checks

    # 3. Sunday at 12:00 UTC (disallowed day)
    tx_sunday = tx_valid.model_copy(update={"timestamp": datetime(2026, 8, 16, 12, 0, 0, tzinfo=timezone.utc)}) # Sunday
    res_sunday = check_authorization(tx_sunday, mandate)
    assert res_sunday.passed is False
    assert "outside_time_window" in res_sunday.failed_checks


def test_cumulative_period_caps():
    mandate = Mandate(
        id="mandate_period_caps",
        agent_id="agent_shopping_01",
        per_transaction_cap=30000.0,
        categories=["electronics"],
        merchants=["Amazon"],
        time_window_start="00:00",
        time_window_end="23:59",
        issued_at=datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        ttl_seconds=3600000,
        period_caps={"daily": 40000.0, "monthly": 100000.0},
    )

    base_ts = datetime(2026, 8, 20, 14, 0, 0, tzinfo=timezone.utc)
    prior_txs = [
        {"id": "tx_p1", "amount": 25000.0, "timestamp": (base_ts - timedelta(hours=3)).isoformat(), "decision": "ALLOW"},
    ]

    # Current tx is ₹20,000 (individually < 30,000 cap, but 25k + 20k = 45k > daily 40k cap)
    tx = TransactionRequest(
        id="tx_cap_test",
        agent_id="agent_shopping_01",
        mandate_id="mandate_period_caps",
        user_intent_id="intent_001",
        claimed_product={"brand": "Sony"},
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        amount=20000.0,
        category="electronics",
        merchant="Amazon",
        timestamp=base_ts,
        scenario_type="legitimate_unusual",
        expected_decision="BLOCK",
    )

    res = check_authorization(tx, mandate, prior_transactions=prior_txs)
    assert res.passed is False
    assert "period_cap_exceeded_daily" in res.failed_checks


# -----------------------------------------------------------------------------
# TASK 6 TESTS: Weighted Preference Scoring & Goal Drift
# -----------------------------------------------------------------------------
def test_weighted_soft_preference_scoring():
    product = Product(
        sku="ELEC-SONY-WH1000XM5-BLK",
        brand="Sony",
        model="WH-1000XM5",
        category="electronics",
        price=29990.0,
        specs={"color": "black", "anc": True, "battery": "30h"},
    )

    # User heavily weights noise-cancelling (1.0), moderately weights color (0.5), light on connectivity (0.1)
    intent = UserIntent(
        id="intent_weighted",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5"},
        soft_preferences={
            "color": {"val": "black", "weight": 0.5},
            "anc": {"val": True, "weight": 1.0},
            "battery": {"val": "50h", "weight": 0.5}, # Mismatch
        },
        substitution_allowed=False,
        created_at=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
    )

    res = check_intent_fidelity(intent, product)
    assert res.hard_match is True
    # matched weights: color (0.5) + anc (1.0) = 1.5; total weights = 2.0 -> score = 0.75
    assert res.soft_score == 0.75


def test_session_goal_drift_detection():
    session = PurchaseSession(
        session_id="sess_drift_01",
        intent_id="intent_001",
        agent_id="agent_shopping_01",
        declared_item_count=1,
        declared_total_budget=35000.0,
        created_at=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
    )

    # 1. No drift on fresh session
    drift_0 = check_goal_drift(session, [])
    assert drift_0.has_drift is False

    # 2. Drift on exceeding declared single item
    session_txs = [
        {"id": "tx_1", "amount": 29990.0, "decision": "ALLOW"},
    ]
    drift_item = check_goal_drift(session, session_txs)
    assert drift_item.has_drift is True
    assert drift_item.reason == "declared_item_count_exceeded"

    # 3. Drift on excessive retries
    session_retries = [
        {"id": "tx_b1", "decision": "BLOCK"},
        {"id": "tx_b2", "decision": "BLOCK"},
        {"id": "tx_b3", "decision": "BLOCK"},
    ]
    drift_retries = check_goal_drift(session, session_retries)
    assert drift_retries.has_drift is True
    assert drift_retries.reason == "excessive_session_retries"


# -----------------------------------------------------------------------------
# TASK 7 TESTS: Multi-Source Evidence & Freshness TTL
# -----------------------------------------------------------------------------
def test_multi_source_evidence_resolution_and_freshness():
    catalog = get_catalog()
    now = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Record 1: checkout_sku price (most authoritative, fresh)
    rec_checkout = EvidenceSourceRecord(
        source="checkout_sku",
        field="price",
        value=29990.0,
        retrieved_at=now - timedelta(minutes=5),
        ttl_seconds=1800,
    )

    # Record 2: merchant spec with stale TTL
    rec_stale = EvidenceSourceRecord(
        source="merchant_structured_spec",
        field="color",
        value="black",
        retrieved_at=now - timedelta(hours=30), # Expired (TTL 24h)
        ttl_seconds=86400,
    )

    claimed = {"brand": "Sony", "model": "WH-1000XM5", "price": 29990.0, "color": "black"}
    res = check_evidence(
        claimed_product=claimed,
        actual_sku="ELEC-SONY-WH1000XM5-BLK",
        catalog=catalog,
        multi_source_records=[rec_checkout, rec_stale],
        current_time=now,
    )

    assert "checkout_sku" in res.sources_checked
    assert "merchant_structured_spec" in res.sources_checked
    # Stale record flagged as conflict
    stale_conflicts = [c for c in res.conflicts if c.get("actual") == "stale_evidence"]
    assert len(stale_conflicts) == 1
    assert stale_conflicts[0]["field"] == "color"


# -----------------------------------------------------------------------------
# TASK 8 TESTS: Provenance Hash Chaining & Tamper Verification
# -----------------------------------------------------------------------------
def test_provenance_cryptographic_hash_chaining():
    catalog = get_catalog()
    intent = UserIntent(
        id="intent_hash_test",
        agent_id="agent_shopping_01",
        hard_requirements={"brand": "Sony", "model": "WH-1000XM5"},
        soft_preferences={"color": "black"},
        substitution_allowed=False,
        created_at=datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
    )

    trail = build_provenance_trail(
        transaction_id="tx_hash_verify",
        intent=intent,
        catalog=catalog,
        selected_sku="ELEC-SONY-WH1000XM5-BLK",
    )

    assert len(trail) >= 4
    # Event 1 must have prev_hash = "genesis"
    assert trail[0]["prev_hash"] == "genesis"
    assert trail[0]["event_hash"] is not None

    # Check linkage
    for i in range(1, len(trail)):
        assert trail[i]["prev_hash"] == trail[i - 1]["event_hash"]

    # Verify chain validity
    is_valid, err = verify_provenance_chain(trail)
    assert is_valid is True
    assert err is None

    # Tamper with an event payload
    tampered_trail = [dict(e) for e in trail]
    tampered_trail[1]["payload"] = {"tampered": True}
    is_valid_tampered, err_tampered = verify_provenance_chain(tampered_trail)
    assert is_valid_tampered is False
    assert "Tampered event payload" in err_tampered
