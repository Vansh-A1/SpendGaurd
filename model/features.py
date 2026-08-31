import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "amount_ratio",
    "category_novelty",
    "merchant_novelty",
    "trailing_1h_count",
    "trailing_24h_sum",
    "rolling_sum_ratio",
    "time_deviation",
    "amount_zscore",
    "is_new_agent",
    "cap_proximity",
    "velocity_saturation",
    "rolling_cap_overflow",
    "session_cum_spend_ratio",
    "session_cap_overflow",
]


def load_mandates_dict(mandates_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    if mandates_path is None:
        mandates_path = Path(__file__).resolve().parent.parent / "data" / "mandates.json"
    with open(mandates_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {m["id"]: m for m in data}


def _clock_time_hours(dt: datetime) -> float:
    """Convert timestamp to decimal hours in [0, 24)."""
    return dt.hour + dt.minute / 60.0 + dt.second / 3600.0


def engineer_features(
    scenarios_df: pd.DataFrame,
    mandates_dict: Optional[Dict[str, Dict[str, Any]]] = None,
) -> pd.DataFrame:
    """
    Computes 9 behavioral risk features per transaction row:
    1. amount_ratio: amount / mandate.per_transaction_cap
    2. category_novelty: 1 if first transaction in this category for this agent, else 0
    3. merchant_novelty: 1 if first transaction with this merchant for this agent, else 0
    4. trailing_1h_count: number of prior transactions by this agent in [t - 1h, t)
    5. trailing_24h_sum: sum of prior transaction amounts by this agent in [t - 24h, t)
    6. rolling_sum_ratio: (trailing_1h_sum + this.amount) / mandate.per_transaction_cap
    7. time_deviation: abs(this.clock_time - mean(prior.clock_times)) or 0 if first tx
    8. amount_zscore: (amount - mean(priors)) / std(priors) (0 if < 3 priors or std=0)
    9. is_new_agent: 1 if < 5 prior transactions for this agent, else 0
    
    All features computed strictly in chronological order without lookahead.
    """
    if mandates_dict is None:
        mandates_dict = load_mandates_dict()

    df = scenarios_df.copy()
    
    # Store original row order
    original_index = df.index
    
    # Parse timestamp as datetime if it is string
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["_parsed_ts"] = pd.to_datetime(df["timestamp"], format="mixed", utc=True)
    else:
        df["_parsed_ts"] = pd.to_datetime(df["timestamp"], utc=True)

    # Ensure amount is float
    df["amount"] = df["amount"].astype(float)

    # Sort strictly chronologically
    df = df.sort_values(by=["_parsed_ts", "id"]).reset_index()

    feature_rows = []

    # Process per agent history sequentially
    agent_histories: Dict[str, List[Dict[str, Any]]] = {}
    session_spends: Dict[str, float] = {}

    for _, row in df.iterrows():
        agent_id = row["agent_id"]
        mandate_id = row["mandate_id"]
        mandate = mandates_dict.get(mandate_id, {})
        cap = float(mandate.get("per_transaction_cap", 40000.0))
        amt = float(row["amount"])
        cat = row["category"]
        merch = row["merchant"]
        ts = row["_parsed_ts"].to_pydatetime()
        clock_h = _clock_time_hours(ts)

        all_priors = agent_histories.get(agent_id, [])

        # Bound history to a 14-day rolling window to prevent stale cross-session state leakage
        window_cutoff = ts - timedelta(days=14)
        priors = [p for p in all_priors if p["ts"] >= window_cutoff]

        # 1. amount_ratio
        amount_ratio = amt / cap if cap > 0 else 0.0

        # 2. category_novelty (evaluated against agent lifetime history)
        prior_categories = {p["category"] for p in all_priors}
        category_novelty = 1 if cat not in prior_categories else 0

        # 3. merchant_novelty (evaluated against agent lifetime history)
        prior_merchants = {p["merchant"] for p in all_priors}
        merchant_novelty = 1 if merch not in prior_merchants else 0

        # 4. trailing_1h_count & trailing 1h sum
        one_hour_ago = ts - timedelta(hours=1)
        prior_1h = [p for p in priors if one_hour_ago <= p["ts"] < ts]
        trailing_1h_count = len(prior_1h)
        trailing_1h_sum = sum(p["amount"] for p in prior_1h)

        # 5. trailing_24h_sum
        twenty_four_hours_ago = ts - timedelta(hours=24)
        prior_24h = [p for p in priors if twenty_four_hours_ago <= p["ts"] < ts]
        trailing_24h_sum = sum(p["amount"] for p in prior_24h)

        # 6. rolling_sum_ratio (including this transaction)
        rolling_sum_ratio = (trailing_1h_sum + amt) / cap if cap > 0 else 0.0

        # 7. time_deviation (exponential decay weighted over rolling window)
        if len(priors) > 0:
            weights = np.array([
                np.exp(-(ts - p["ts"]).total_seconds() / (7.0 * 86400.0))
                for p in priors
            ])
            weights_sum = weights.sum()
            if weights_sum > 0:
                weights /= weights_sum
                mean_clock_h = float(np.sum(weights * np.array([p["clock_h"] for p in priors])))
                time_deviation = abs(clock_h - mean_clock_h)
            else:
                time_deviation = 0.0
        else:
            time_deviation = 0.0

        # 8. amount_zscore (exponential decay weighted over rolling window)
        if len(priors) >= 3:
            prior_amts = np.array([p["amount"] for p in priors])
            weights = np.array([
                np.exp(-(ts - p["ts"]).total_seconds() / (7.0 * 86400.0))
                for p in priors
            ])
            weights_sum = weights.sum()
            if weights_sum > 0:
                weights /= weights_sum
                mean_amt = float(np.sum(weights * prior_amts))
                variance = float(np.sum(weights * ((prior_amts - mean_amt) ** 2)))
                std_amt = np.sqrt(variance)
                if std_amt > 1e-4:
                    amount_zscore = (amt - mean_amt) / std_amt
                else:
                    amount_zscore = 0.0
            else:
                amount_zscore = 0.0
        else:
            amount_zscore = 0.0

        # 9. is_new_agent
        is_new_agent = 1 if len(all_priors) < 5 else 0

        # 10. cap_proximity (continuous measure of proximity to mandate per-transaction cap)
        cap_proximity = round(float(np.clip((amount_ratio - 0.70) / 0.30, 0.0, 1.0)), 4)

        # 11. velocity_saturation (non-linear saturating velocity indicator: min(1.0, count / 3.0))
        velocity_saturation = round(float(min(1.0, trailing_1h_count / 3.0)), 4)

        # 12. rolling_cap_overflow (how far rolling 1h spend exceeds the per-transaction cap: max(0.0, rolling_sum_ratio - 1.0))
        rolling_cap_overflow = round(float(max(0.0, rolling_sum_ratio - 1.0)), 4)

        # 13. session_cum_spend_ratio (cumulative session spend / declared budget, degrading to 0.0 if session_id is None)
        # 14. session_cap_overflow (how far declared session budget exceeds per-transaction cap: max(0.0, (budget / cap) - 1.0))
        session_id = row.get("session_id") if "session_id" in row and pd.notna(row.get("session_id")) else None
        session_cum_spend_ratio = 0.0
        session_cap_overflow = 0.0
        if session_id:
            try:
                from session.manager import get_session
                sess = get_session(str(session_id))
                if sess and sess.declared_total_budget and sess.declared_total_budget > 0:
                    accum_spend = session_spends.get(str(session_id), 0.0)
                    session_cum_spend_ratio = round(float((accum_spend + amt) / float(sess.declared_total_budget)), 4)
                    session_spends[str(session_id)] = accum_spend + amt
                    session_cap_overflow = round(float(max(0.0, (float(sess.declared_total_budget) / cap) - 1.0)), 4)
            except Exception:
                session_cum_spend_ratio = 0.0
                session_cap_overflow = 0.0

        feat_dict = {
            "index": row["index"],
            "amount_ratio": round(amount_ratio, 4),
            "category_novelty": category_novelty,
            "merchant_novelty": merchant_novelty,
            "trailing_1h_count": trailing_1h_count,
            "trailing_24h_sum": round(trailing_24h_sum, 2),
            "rolling_sum_ratio": round(rolling_sum_ratio, 4),
            "time_deviation": round(time_deviation, 4),
            "amount_zscore": round(amount_zscore, 4),
            "is_new_agent": is_new_agent,
            "cap_proximity": cap_proximity,
            "velocity_saturation": velocity_saturation,
            "rolling_cap_overflow": rolling_cap_overflow,
            "session_cum_spend_ratio": session_cum_spend_ratio,
            "session_cap_overflow": session_cap_overflow,
        }
        feature_rows.append(feat_dict)

        # Append to agent history for subsequent rows
        if agent_id not in agent_histories:
            agent_histories[agent_id] = []
        agent_histories[agent_id].append({
            "ts": ts,
            "amount": amt,
            "category": cat,
            "merchant": merch,
            "clock_h": clock_h,
        })

    feat_df = pd.DataFrame(feature_rows).set_index("index").reindex(original_index)
    return feat_df[FEATURE_COLUMNS]
