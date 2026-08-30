import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import csv
import json
import pickle
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Literal, Optional, Tuple
import pandas as pd
import numpy as np
from sklearn.metrics import precision_score, recall_score, f1_score, precision_recall_curve, auc, brier_score_loss

from data.schema import TransactionRequest, Product
from policy.schema import Mandate
from intent.schema import UserIntent
from data.catalog import get_catalog
from policy.authorization import check_authorization
from intent.fidelity import check_intent_fidelity
from evidence.check import check_evidence
from model.features import engineer_features
from model.explain import explain_risk
from decision.engine import evaluate_transaction, DecisionReceipt


REPO_ROOT = Path(__file__).resolve().parent.parent


def load_canonical_dataset() -> Tuple[List[TransactionRequest], Dict[str, Mandate], Dict[str, UserIntent], List[Product], Any, pd.DataFrame]:
    catalog = get_catalog()
    with open(REPO_ROOT / "data" / "mandates.json") as f:
        mandates = {m["id"]: Mandate(**m) for m in json.load(f)}
    with open(REPO_ROOT / "data" / "intents.json") as f:
        intents = {k: UserIntent(**v) for k, v in json.load(f).items()}
    with open(REPO_ROOT / "model" / "risk_model.pkl", "rb") as f:
        risk_model = pickle.load(f)

    df_110 = pd.read_csv(REPO_ROOT / "data" / "scenarios.csv")
    requests = []
    for _, row in df_110.iterrows():
        tx = TransactionRequest(
            id=row["id"],
            agent_id=row["agent_id"],
            mandate_id=row["mandate_id"],
            user_intent_id=row["user_intent_id"],
            claimed_product=json.loads(row["claimed_product"]),
            actual_sku=row["actual_sku"],
            amount=float(row["amount"]),
            category=row["category"],
            merchant=row["merchant"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            scenario_type=row["scenario_type"],
            expected_decision=row["expected_decision"],
            session_id=row["session_id"] if pd.notna(row["session_id"]) else None,
            intent_version=int(row.get("intent_version", 1)),
        )
        requests.append(tx)

    return requests, mandates, intents, catalog, risk_model, df_110


def evaluate_ablation(
    config: Literal["baseline_a", "baseline_b", "baseline_c", "baseline_d", "final_spendguard"],
    transaction: TransactionRequest,
    mandate: Mandate,
    intent: UserIntent,
    catalog: List[Product],
    risk_model: Any,
    history_df: Optional[pd.DataFrame] = None,
) -> str:
    """
    Evaluates transaction under specific ablation baseline configurations:
    - baseline_a: Authorization only (Pillar 1)
    - baseline_b: Authorization + Intent Fidelity (Pillars 1+2)
    - baseline_c: Authorization + Intent Fidelity + Evidence (Pillars 1+2+4, No ML)
    - baseline_d: Authorization + Intent Fidelity + Behavioral Risk (Pillars 1+2+3, No Evidence)
    - final_spendguard: All four pillars
    """
    if config == "final_spendguard":
        receipt = evaluate_transaction(transaction, mandate, intent, catalog, risk_model, history_df=history_df)
        return receipt.decision

    # 1. Step 1: Authorization
    auth_result = check_authorization(transaction, mandate)
    if not auth_result.passed:
        return "BLOCK"
    if auth_result.is_stale and config in ("baseline_a", "baseline_b", "baseline_c", "baseline_d"):
        # Stale mandate nudge ceiling
        return "VERIFY"

    if config == "baseline_a":
        return "ALLOW"

    # 2. Step 2: Intent Fidelity
    actual_product = next((p for p in catalog if p.sku == transaction.actual_sku), None)
    if actual_product is None:
        actual_product = Product(
            sku=transaction.actual_sku, brand="Unknown", model="Unknown",
            category=transaction.category, price=transaction.amount, specs={},
        )

    intent_result = check_intent_fidelity(intent, actual_product)
    if not intent_result.hard_match:
        return "BLOCK"
    if intent_result.soft_score <= 0.50 and config in ("baseline_b", "baseline_c"):
        return "VERIFY"

    if config == "baseline_b":
        return "ALLOW"

    # 3. Step 3: Evidence Check (Pillar 4) - active in baseline_c and final
    evidence_unverifiable = False
    evidence_soft_conflict = False
    if config in ("baseline_c", "final_spendguard"):
        evidence_result = check_evidence(transaction.claimed_product, transaction.actual_sku, catalog)
        hard_keys = set(intent.hard_requirements.keys()) if intent and intent.hard_requirements else set()
        if evidence_result.conflicts:
            hard_conflicts = [c for c in evidence_result.conflicts if c["field"] in hard_keys or c["field"] == "sku"]
            if hard_conflicts:
                return "BLOCK"
            evidence_soft_conflict = True
        if evidence_result.unverifiable_attributes:
            evidence_unverifiable = True

        if config == "baseline_c":
            if evidence_soft_conflict or evidence_unverifiable or (intent_result.soft_score <= 0.50):
                return "VERIFY"
            return "ALLOW"

    # 4. Step 4: Behavioral Risk (Pillar 3) - active in baseline_d
    if config == "baseline_d":
        if history_df is not None and not history_df.empty:
            tx_row = transaction.model_dump(mode="json")
            tx_row["claimed_product"] = json.dumps(tx_row["claimed_product"])
            combined_df = pd.concat([history_df, pd.DataFrame([tx_row])], ignore_index=True)
            feats_all = engineer_features(combined_df)
            feat_df = feats_all.iloc[[-1]]
        else:
            tx_row = transaction.model_dump(mode="json")
            tx_row["claimed_product"] = json.dumps(tx_row["claimed_product"])
            feat_df = engineer_features(pd.DataFrame([tx_row]))

        risk_score = float(risk_model.predict_proba(feat_df)[:, 1][0]) if risk_model else 0.1
        is_nudge = auth_result.is_stale or (intent_result.soft_score <= 0.50)
        if is_nudge:
            return "VERIFY"
        if risk_score < 0.30:
            return "ALLOW"
        elif risk_score < 0.75:
            return "VERIFY"
        else:
            return "BLOCK"

    return "ALLOW"


def run_ablation_study():
    requests, mandates, intents, catalog, risk_model, df_110 = load_canonical_dataset()
    configs = ["baseline_a", "baseline_b", "baseline_c", "baseline_d", "final_spendguard"]
    config_labels = {
        "baseline_a": "Baseline A (Auth Only / P1)",
        "baseline_b": "Baseline B (Auth + Intent / P1+P2)",
        "baseline_c": "Baseline C (Auth + Intent + Evidence / P1+P2+P4)",
        "baseline_d": "Baseline D (Auth + Intent + ML / P1+P2+P3)",
        "final_spendguard": "SpendGuard (Full Hybrid / P1+P2+P3+P4)",
    }

    results = {}
    for cfg in configs:
        matches = 0
        fn_count = 0 # attack allowed
        fp_count = 0 # legitimate blocked/held
        by_type = {}

        for idx, tx in enumerate(requests):
            hist = df_110.iloc[:idx]
            mandate = mandates[tx.mandate_id]
            intent = intents[tx.user_intent_id]
            actual_dec = evaluate_ablation(cfg, tx, mandate, intent, catalog, risk_model, history_df=hist)
            is_match = (actual_dec == tx.expected_decision)
            if is_match:
                matches += 1

            st = tx.scenario_type
            if st not in by_type:
                by_type[st] = {"total": 0, "matches": 0}
            by_type[st]["total"] += 1
            if is_match:
                by_type[st]["matches"] += 1

            # Attack escape: expected != ALLOW but actual == ALLOW
            if tx.expected_decision in ("BLOCK", "VERIFY") and actual_dec == "ALLOW":
                fn_count += 1
            # False alarm on legit: expected == ALLOW but actual != ALLOW
            if tx.expected_decision == "ALLOW" and actual_dec != "ALLOW":
                fp_count += 1

        attack_total = sum(1 for tx in requests if tx.expected_decision in ("BLOCK", "VERIFY"))
        legit_total = sum(1 for tx in requests if tx.expected_decision == "ALLOW")

        results[cfg] = {
            "label": config_labels[cfg],
            "total": len(requests),
            "matches": matches,
            "accuracy": matches / len(requests) * 100.0,
            "fn_count": fn_count,
            "fnr": (fn_count / attack_total * 100.0) if attack_total else 0.0,
            "fp_count": fp_count,
            "fpr": (fp_count / legit_total * 100.0) if legit_total else 0.0,
            "by_type": by_type,
        }

    return results


if __name__ == "__main__":
    res = run_ablation_study()
    print("=" * 80)
    print("SPENDGUARD ABLATION STUDY (110 CANONICAL SCENARIOS)")
    print("=" * 80)
    for k, v in res.items():
        print(f"\nConfiguration: {v['label']}")
        print(f"  Match Rate: {v['matches']}/{v['total']} ({v['accuracy']:.2f}%)")
        print(f"  False Negative Rate (Attacks Allowed): {v['fn_count']} attacks ({v['fnr']:.2f}%)")
        print(f"  False Positive Rate (Legit Blocked/Held): {v['fp_count']} ({v['fpr']:.2f}%)")
        print("  Breakdown by Scenario:")
        for st, st_data in v["by_type"].items():
            print(f"    - {st:20s}: {st_data['matches']:2d}/{st_data['total']:2d} ({st_data['matches']/st_data['total']*100:.1f}%)")
