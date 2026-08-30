import json
from pathlib import Path
from typing import List, Dict, Any
import numpy as np


def _format_feature_explanation(feature_name: str, value: float) -> str:
    """Formats an individual feature and value into an interpretable plain-English reason."""
    if feature_name == "rolling_sum_ratio":
        return f"rolling 1-hour spend is {value:.1f}x the per-transaction cap"
    elif feature_name == "amount_ratio":
        return f"transaction amount is {value:.1f}x the per-transaction cap"
    elif feature_name == "trailing_1h_count":
        return f"{int(value)} rapid transaction(s) occurred within the past hour"
    elif feature_name == "trailing_24h_sum":
        return f"trailing 24-hour accumulated spend reached ₹{value:,.2f}"
    elif feature_name == "amount_zscore":
        return f"transaction amount is {value:+.1f} std dev from agent historical average"
    elif feature_name == "category_novelty":
        return "first transaction in this category for this agent" if value == 1 else "standard recurring category"
    elif feature_name == "merchant_novelty":
        return "first transaction with this merchant for this agent" if value == 1 else "known recurring merchant"
    elif feature_name == "time_deviation":
        return f"execution time deviates by {value:.1f} hours from agent historical average"
    elif feature_name == "is_new_agent":
        return "new agent with fewer than 5 historical transactions" if value == 1 else "established agent"
    elif feature_name == "cap_proximity":
        return f"transaction amount sits at {value*100:.0f}% proximity to per-transaction cap (sub-cap split indicator)"
    elif feature_name == "velocity_saturation":
        return f"burst velocity saturation reached {value*100:.0f}% of safety threshold within 1 hour"
    elif feature_name == "rolling_cap_overflow":
        return f"rolling 1-hour spend exceeds per-transaction cap by {value:.2f}x"
    elif feature_name == "session_cum_spend_ratio":
        return f"cumulative session spend reached {value*100:.0f}% of declared budget"
    elif feature_name == "session_cap_overflow":
        return f"declared session budget exceeds per-transaction cap by {value:.2f}x"
    return f"{feature_name} = {value}"


def explain_risk(transaction_features: Dict[str, Any], model: Any) -> List[str]:
    """
    Returns the top 2 features by model feature-importance weighted value for this specific transaction,
    phrased in clear, plain English for inclusion in Decision Receipts.
    """
    # Load column order if available
    cols_file = Path(__file__).resolve().parent / "feature_columns.json"
    if cols_file.exists():
        with open(cols_file, "r", encoding="utf-8") as f:
            feature_cols = json.load(f)
    else:
        feature_cols = list(transaction_features.keys())

    # Get feature importances from model
    if hasattr(model, "feature_importances_"):
        importances = dict(zip(feature_cols, model.feature_importances_))
    else:
        importances = {col: 1.0 for col in feature_cols}

    scored_features = []
    for col in feature_cols:
        val = float(transaction_features.get(col, 0.0))
        imp = importances.get(col, 0.0)
        
        # Calculate impact score (importance * magnitude / anomaly signal)
        impact = imp * abs(val)
        scored_features.append((col, val, impact))

    # Sort descending by impact
    scored_features.sort(key=lambda x: x[2], reverse=True)

    # Pick top 2 non-zero / highest impact features
    top_2 = scored_features[:2]
    explanations = [_format_feature_explanation(col, val) for col, val, _ in top_2]
    return explanations
