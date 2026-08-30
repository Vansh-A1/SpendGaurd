# SpendGuard — Autonomous Agent Trust Layer & Red-Team Simulation Lab

SpendGuard is a four-pillar trust gate that intercepts autonomous AI purchasing agents before money moves through payment rails (e.g. Razorpay test mode). It deterministically validates authority, intent fidelity, merchant evidence, and behavioral risk to eliminate agent hallucination, social engineering, and prompt injection attacks.

---

## 🏛️ Four Trust Pillars

1. **Authority** (`policy/`): Deterministic validation against corporate mandates (budget caps, category constraints, whitelisted merchants, time windows, mandate freshness).
2. **Intent Fidelity** (`intent/`): Deep verification against user intent (hard requirements vs weighted soft preferences).
3. **Behavioral Risk** (`model/`): XGBoost behavioral classifier detecting burst transactions, split-payment evasion, and anomalies.
4. **Evidence & Provenance** (`evidence/`): Cryptographically chained provenance verification cross-referencing agent claims against ground-truth catalog specs.

### Trust Gate Outcomes (`decision/`)
- `ALLOW`: Direct pass-through $\rightarrow$ Razorpay test-mode order captured immediately.
- `VERIFY`: Pre-authorization hold $\rightarrow$ Human operator verification queue with SLA timeout.
- `BLOCK`: Hard stop $\rightarrow$ Payment rejected, zero liability.

*Core Invariant: Machine learning never overrides a deterministic failure.*

---

## 🧪 Live Agent Red-Team Simulation Lab (`simulator/` & `agent/`)

SpendGuard features a closed-loop, adversarial simulation harness: a tool-using AI shopping agent navigates a self-hosted "trap" catalog seeded with easy, subtle, and adversarial attacks.

### Adversarial Trap Archetypes
- **Spec Spoofing**: Listing claims 32GB RAM / 1TB SSD while underlying barcode is 8GB/256GB (*Caught by Evidence*).
- **Price-Split Bait**: Prompting agent to purchase multiple micro-vouchers to bypass single transaction limits (*Caught by Behavioral Risk*).
- **Urgency / Social Engineering**: Fake "Only 1 Left" bundles pushing orders over budget (*Caught by Authority*).
- **Near-Miss Substitution**: Substituting unavailable items with close alternatives (*Held for Operator Review*).
- **Category Creep**: Nudging an IT procurement agent into unauthorized non-work items (*Caught by Authority*).
- **Multi-Step Drift**: Sneaking in budget overruns during multi-item sessions (*Caught by Session Drift*).

### Red-Team Security Metrics
| Metric | Definition | Benchmark |
|---|---|---|
| **True Leakage Rate** | % of flawed/trap tasks that completed end-to-end (Headline Metric) | **0.0%** |
| **Flagged Rate** | % of trap attempts stopped or held by SpendGuard | **100.0%** |
| **Agent Fool Rate** | % of trap tasks where the agent attempted the flawed purchase | **100.0%** |
| **False Friction Rate** | % of clean baseline tasks incorrectly delayed | **0.0%** |

---

## 🔐 Environment Configuration & Access Control

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

### Environment Variables
```bash
# Gateway & Web
FRONTEND_URL=http://localhost:3000
JWT_SECRET=replace-with-a-32-character-random-secret

# Demo & Operator Credentials (Auto-generated on startup if left unset)
ADMIN_EMAIL=admin@spendguard.ai
ADMIN_PASSWORD=
OPERATOR_EMAIL=operator@spendguard.ai
OPERATOR_PASSWORD=
VIEWER_EMAIL=viewer@spendguard.ai
VIEWER_PASSWORD=

# Live LLM Simulation & Safety Budget Guards
LLM_PROVIDER=fallback       # Options: openai | anthropic | gemini | ollama | fallback
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
MAX_SIMULATION_RUNS_PER_BATCH=20
MAX_LLM_CALLS_PER_DAY=100
```

> [!NOTE]
> If passwords are left empty in `.env`, SpendGuard generates cryptographically secure random passwords using `secrets.token_urlsafe` and prints them prominently inside a startup banner on initial initialization.

---

## 🚀 Running Locally

### 1. Start the Backend API
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the Frontend Console
```bash
cd frontend
yarn start
```
Access the application at `http://localhost:3000`. Click **"Open Console →"** to access the **Simulation Lab**, **Verification Queue**, and **Transaction Trails**.

---

## 🧪 Testing

Run the full pytest suite (73 automated tests covering all 4 pillars, payments, sessions, and red-team simulation):
```bash
PYTHONPATH=. pytest tests/ -v
```
