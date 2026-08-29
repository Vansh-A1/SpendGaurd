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
        df["_parsed_ts"] = pd.to_datetime(df["timestamp"], utc=True)
    else:
        df["_parsed_ts"] = df["timestamp"]

    # Ensure amount is float
    df["amount"] = df["amount"].astype(float)

    # Sort strictly chronologically
    df = df.sort_values(by=["_parsed_ts", "id"]).reset_index()

    feature_rows = []

    # Process per agent history sequentially
    agent_histories: Dict[str, List[Dict[str, Any]]] = {}

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

        priors = agent_histories.get(agent_id, [])

        # 1. amount_ratio
        amount_ratio = amt / cap if cap > 0 else 0.0

        # 2. category_novelty
        prior_categories = {p["category"] for p in priors}
        category_novelty = 1 if cat not in prior_categories else 0

        # 3. merchant_novelty
        prior_merchants = {p["merchant"] for p in priors}
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

        # 7. time_deviation
        if len(priors) > 0:
            mean_clock_h = np.mean([p["clock_h"] for p in priors])
            time_deviation = abs(clock_h - mean_clock_h)
        else:
            time_deviation = 0.0

        # 8. amount_zscore
        if len(priors) >= 3:
            prior_amts = [p["amount"] for p in priors]
            std_amt = np.std(prior_amts)
            if std_amt > 1e-6:
                amount_zscore = (amt - np.mean(prior_amts)) / std_amt
            else:
                amount_zscore = 0.0
        else:
            amount_zscore = 0.0

        # 9. is_new_agent
        is_new_agent = 1 if len(priors) < 5 else 0

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
