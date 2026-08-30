import json
import pickle
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    confusion_matrix,
    classification_report,
    brier_score_loss,
)
from xgboost import XGBClassifier

# Add repo root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model.features import engineer_features, FEATURE_COLUMNS


def train_risk_model():
    repo_root = Path(__file__).resolve().parent.parent
    train_scenarios_csv = repo_root / "data" / "train_scenarios.csv"
    scenarios_csv = repo_root / "data" / "scenarios.csv"
    
    csv_to_use = train_scenarios_csv if train_scenarios_csv.exists() else scenarios_csv
    model_path = repo_root / "model" / "risk_model.pkl"
    feature_cols_path = repo_root / "model" / "feature_columns.json"

    # Step 1: Load data
    df = pd.read_csv(csv_to_use)
    print(f"Loaded {len(df)} transactions from {csv_to_use}")

    # Step 2: Feature engineering
    X = engineer_features(df)
    
    # Step 3: Binary label (Behavioral Risk Model targets Split-Payment attacks and velocity anomalies)
    y = (df["scenario_type"] == "split_payment").astype(int)

    print(f"Feature matrix shape: {X.shape}, Positive split payments: {(y==1).sum()}, Benign: {(y==0).sum()}\n")

    # Step 4: Train / Test Split (80/20 Stratified)
    X_train, X_test, y_train, y_test, df_train, df_test = train_test_split(
        X, y, df, test_size=0.20, random_state=42, stratify=y
    )

    monotone_constraints = tuple(
        1 if c in ["velocity_saturation", "rolling_cap_overflow", "rolling_sum_ratio", "trailing_1h_count", "session_cum_spend_ratio", "session_cap_overflow"] else 0
        for c in FEATURE_COLUMNS
    )

    # Step 5: Train XGBoost Classifier on Train Split
    model = XGBClassifier(
        n_estimators=75,
        max_depth=3,
        learning_rate=0.10,
        gamma=0.1,
        subsample=0.8,
        colsample_bytree=0.6,
        scale_pos_weight=1.0,
        monotone_constraints=monotone_constraints,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    # Step 6: Evaluate on Test Set
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    cm = confusion_matrix(y_test, y_pred)
    brier = brier_score_loss(y_test, y_proba)

    print("=" * 50)
    print("XGBoost Behavioral Risk Model Test Evaluation:")
    print(f"  Accuracy:    {acc:.4f}")
    print(f"  Precision:   {prec:.4f}")
    print(f"  Recall:      {rec:.4f}")
    print(f"  F1 Score:    {f1:.4f}")
    print(f"  Brier Score: {brier:.4f}")
    print("\nConfusion Matrix [TN, FP / FN, TP]:")
    print(cm)
    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred, target_names=["Benign (0)", "Risk (1)"]))
    print("=" * 50)

    # Step 7: Fit Final Production Model on full training dataset
    prod_model = XGBClassifier(
        n_estimators=75,
        max_depth=3,
        learning_rate=0.10,
        gamma=0.1,
        subsample=0.8,
        colsample_bytree=0.6,
        scale_pos_weight=1.0,
        monotone_constraints=monotone_constraints,
        eval_metric="logloss",
        random_state=42,
    )
    prod_model.fit(X, y)

    # Feature Importances from production model
    importances = dict(zip(FEATURE_COLUMNS, [round(float(v), 4) for v in prod_model.feature_importances_]))
    sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    print("\nFeature Importances (Regularized Production Model):")
    for feat, imp in sorted_imp:
        print(f"  {feat:24s}: {imp:.4f}")

    # Step 8: Sanity Table: Mean predicted risk score per scenario_type on canonical 110 scenarios
    df_110 = pd.read_csv(scenarios_csv)
    X_110 = engineer_features(df_110)
    all_probas_110 = prod_model.predict_proba(X_110)[:, 1]
    df_110["predicted_risk_score"] = all_probas_110

    sanity_df = df_110.groupby("scenario_type")["predicted_risk_score"].agg(["count", "mean", "min", "max"]).reset_index()
    sanity_df = sanity_df.sort_values(by="mean", ascending=False)
    print("\nSanity Check: Mean Predicted Risk Probability on Canonical 110 Scenarios:")
    print(sanity_df.to_string(index=False))

    # Step 9: Save Model Artifacts
    with open(model_path, "wb") as f:
        pickle.dump(prod_model, f)
    with open(feature_cols_path, "w", encoding="utf-8") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)

    print(f"\nSaved model to {model_path}")
    print(f"Saved feature column schema to {feature_cols_path}")

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "brier_score": brier,
        "feature_importances": importances,
        "confusion_matrix": cm.tolist(),
        "sanity_table": sanity_df.to_dict(orient="records"),
    }


if __name__ == "__main__":
    train_risk_model()
