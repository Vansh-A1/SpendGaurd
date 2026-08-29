import json
import pickle
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix, classification_report
from xgboost import XGBClassifier

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model.features import engineer_features, FEATURE_COLUMNS


def train_risk_model():
    repo_root = Path(__file__).resolve().parent.parent
    scenarios_csv = repo_root / "data" / "scenarios.csv"
    model_path = repo_root / "model" / "risk_model.pkl"
    feature_cols_path = repo_root / "model" / "feature_columns.json"

    # Step 1: Load data
    df = pd.read_csv(scenarios_csv)
    print(f"Loaded {len(df)} transactions from {scenarios_csv}")

    # Step 2: Feature engineering
    X = engineer_features(df)
    
    # Step 3: Binary label
    # 1 for transactions that represent risk patterns (split_payment, budget_violation, wrong_product, evidence_conflict)
    # 0 for benign/novel patterns (legitimate_unusual, substitution, stale_mandate)
    RISK_SCENARIOS = {"split_payment", "budget_violation", "wrong_product", "evidence_conflict"}
    y = df["scenario_type"].apply(lambda st: 1 if st in RISK_SCENARIOS else 0)

    print(f"Feature matrix shape: {X.shape}, Label distribution:\n{y.value_counts().to_dict()}\n")

    # Step 4: Train / Test Split (80/20 Stratified)
    X_train, X_test, y_train, y_test, df_train, df_test = train_test_split(
        X, y, df, test_size=0.20, random_state=42, stratify=y
    )

    # Step 5: Train XGBoost Classifier
    model = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    # Step 6: Evaluate on Test Set
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)

    print("=" * 50)
    print("XGBoost Behavioral Risk Model Test Evaluation:")
    print(f"  Precision: {prec:.4f}")
    print(f"  Recall:    {rec:.4f}")
    print(f"  F1 Score:  {f1:.4f}")
    print("\nConfusion Matrix [TN, FP / FN, TP]:")
    print(cm)
    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Benign (0)", "Risk (1)"]))
    print("=" * 50)

    # Step 7: Sanity Table: Mean predicted risk score per scenario_type
    all_probas = model.predict_proba(X)[:, 1]
    df["predicted_risk_score"] = all_probas

    sanity_df = df.groupby("scenario_type")["predicted_risk_score"].agg(["count", "mean", "min", "max"]).reset_index()
    sanity_df = sanity_df.sort_values(by="mean", ascending=False)
    print("\nSanity Check: Mean Predicted Risk Probability by Scenario Type:")
    print(sanity_df.to_string(index=False))

    # Step 8: Save Model Artifacts
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    with open(feature_cols_path, "w", encoding="utf-8") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)

    print(f"\nSaved model to {model_path}")
    print(f"Saved feature column schema to {feature_cols_path}")

    return {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "confusion_matrix": cm.tolist(),
        "sanity_table": sanity_df.to_dict(orient="records"),
    }


if __name__ == "__main__":
    train_risk_model()
