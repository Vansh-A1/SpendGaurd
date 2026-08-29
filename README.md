# SpendGuard

SpendGuard is a trust layer that sits between an AI agent making a purchase on a human's behalf and the actual payment executing — it checks whether the purchase is authorized, whether it matches what the human actually asked for, whether the agent's behavior looks normal, and whether the agent's claims about the product are true, before letting money move.

## Architecture: Four Pillars

1. **Authorization** (`/policy`): Deterministic checks (budget cap, category, merchant, time window, mandate freshness).
2. **Intent Fidelity** (`/intent`): Deterministic attribute matching (hard requirements vs soft preferences).
3. **Behavioral Risk** (`/model`): Machine Learning (XGBoost/LightGBM) for velocity, split-payment detection, and pattern anomalies.
4. **Evidence** (`/evidence`): Deterministic verification between agent claims and merchant catalog/SKU specs.

### Trust Gate (`/decision`)
Combines pillar results into one of:
- `ALLOW`: Trigger Razorpay test-mode order (`/payments`).
- `VERIFY`: Hold for explicit human approval.
- `BLOCK`: Stop transaction immediately.

*Rule: ML never overrides a deterministic failure.*

## Project Structure
- `data/`: Catalogs, synthetic datasets, and transaction logs.
- `policy/`: Authorization & mandate validation.
- `intent/`: Hard/soft requirement extraction & matching.
- `model/`: Behavioral risk ML model & feature engineering.
- `evidence/`: Spec & SKU evidence verification.
- `decision/`: Trust Gate & Decision Receipt generation.
- `api/`: FastAPI endpoints.
- `payments/`: Razorpay payment execution integration.
- `frontend/`: Dashboard & human-in-the-loop review interface.
