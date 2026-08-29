import json
import pickle
from pathlib import Path
import pandas as pd
import pytest

from model.features import engineer_features, FEATURE_COLUMNS
from model.explain import explain_risk


@pytest.fixture
def sample_scenarios_df():
    repo_root = Path(__file__).resolve().parent.parent
    return pd.read_csv(repo_root / "data" / "scenarios.csv")


@pytest.fixture
def trained_model():
    repo_root = Path(__file__).resolve().parent.parent
    model_path = repo_root / "model" / "risk_model.pkl"
    with open(model_path, "rb") as f:
        return pickle.load(f)


def test_feature_engineering_structure(sample_scenarios_df):
    features_df = engineer_features(sample_scenarios_df)
    assert list(features_df.columns) == FEATURE_COLUMNS
    assert len(features_df) == len(sample_scenarios_df)
    assert not features_df.isnull().any().any()


def test_split_payment_feature_spike(sample_scenarios_df):
    features_df = engineer_features(sample_scenarios_df)
    split_indices = sample_scenarios_df[sample_scenarios_df["scenario_type"] == "split_payment"].index
    split_features = features_df.loc[split_indices]
    
    # In split payments, rolling_sum_ratio or trailing_1h_count must spike
    assert (split_features["rolling_sum_ratio"] > 1.0).any()
    assert (split_features["trailing_1h_count"] > 1).any()


def test_model_inference_and_separation(sample_scenarios_df, trained_model):
    features_df = engineer_features(sample_scenarios_df)
    probas = trained_model.predict_proba(features_df)[:, 1]
    
    split_scores = probas[sample_scenarios_df["scenario_type"] == "split_payment"]
    legit_scores = probas[sample_scenarios_df["scenario_type"] == "legitimate_unusual"]
    
    assert split_scores.mean() > 0.85
    assert legit_scores.mean() < 0.25
    assert split_scores.mean() > legit_scores.mean() * 3


def test_risk_explanation(trained_model):
    feat = {
        "amount_ratio": 0.8,
        "category_novelty": 1,
        "merchant_novelty": 0,
        "trailing_1h_count": 8,
        "trailing_24h_sum": 240000.0,
        "rolling_sum_ratio": 6.0,
        "time_deviation": 0.5,
        "amount_zscore": 2.1,
        "is_new_agent": 0,
    }
    explanations = explain_risk(feat, trained_model)
    assert len(explanations) == 2
    assert all(isinstance(e, str) for e in explanations)
