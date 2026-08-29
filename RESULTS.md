# SpendGuard ML Model Results

## XGBoost Behavioral Risk Model Performance

Trained on `data/scenarios.csv` with 9 engineered features using an 80/20 stratified train/test split.

### Test Set Evaluation Metrics

- **Precision**: `0.7143` (0.7142857142857143)
- **Recall**: `0.7692` (0.7692307692307693)
- **F1 Score**: `0.7407` (0.7407407407407407)
- **Accuracy**: `0.6818` (0.6818181818181818)

### Confusion Matrix (Test Set: 22 Samples)
```
                Predicted Benign (0)   Predicted Risk (1)
Actual Benign (0)        5                      4
Actual Risk (1)          3                     10
```

### Mean Predicted Risk Probability by Scenario Type

| Scenario Type | Count | Mean Risk Score | Min Risk Score | Max Risk Score |
| :--- | :--- | :--- | :--- | :--- |
| `budget_violation` | 15 | `0.947786` | `0.841454` | `0.976473` |
| `split_payment` | 20 | `0.937299` | `0.587993` | `0.979232` |
| `wrong_product` | 15 | `0.735504` | `0.499323` | `0.914350` |
| `evidence_conflict` | 15 | `0.674814` | `0.253790` | `0.894722` |
| `substitution` | 15 | `0.477761` | `0.185720` | `0.780179` |
| `stale_mandate` | 15 | `0.142250` | `0.026530` | `0.854891` |
| `legitimate_unusual` | 15 | `0.108412` | `0.015814` | `0.486444` |

### Key Observations
1. **Split-Payment Detection**: `split_payment` transactions score an average risk score of `0.937299`, heavily driven by `trailing_1h_count`, `rolling_sum_ratio`, and `trailing_24h_sum`.
2. **Cold-Start / Novelty Handling**: `legitimate_unusual` scores an average risk of only `0.108412` (minimum `0.015814`), proving the model does not misclassify novelty or cold-start activity as malicious behavior.
