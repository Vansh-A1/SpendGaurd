# The Complete Guide to SpendGuard: Architecture, Website Sections, and Operational Console

---

## 1. What is SpendGuard?

### The Core Mission
As AI agents evolve from conversational bots into **autonomous purchasing agents** capable of browsing merchant websites, selecting products, and completing checkout, traditional payment rails face a critical vulnerability: **Authorization is not Intent.**

A standard corporate credit card or API mandate might authorize a purchase of ₹35,000 because it fits within the agent's spending ceiling. However, traditional payment gateways cannot answer crucial questions:
- *Did the user ask for this specific model, or did the agent buy an incompatible substitute?*
- *Is the merchant checkout SKU genuinely what the agent claims it is, or is there an evidence conflict?*
- *Is this single ₹9,000 purchase part of an automated split-payment attack draining funds in rapid bursts?*

**SpendGuard is the Trust & Observability Layer for Autonomous AI Payments.**  
Positioned between the AI Agent and the Payment Gateway (Razorpay), SpendGuard evaluates four independent trust pillars before any money moves.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐     ┌──────────────────┐
│  USER INTENT │ ──► │   AI AGENT   │ ──► │  SPENDGUARD GATEWAY  │ ──► │ RAZORPAY PAYMENT │
└──────────────┘     └──────────────┘     └──────────────────────┘     └──────────────────┘
                                                     │
                                        ┌────────────┴────────────┐
                                        │  1. Authority Check     │
                                        │  2. Intent Fidelity     │
                                        │  3. Behavioral ML Risk  │
                                        │  4. Evidence & Proof    │
                                        └─────────────────────────┘
                                                     │
                                        ┌────────────┴────────────┐
                                        │  ALLOW  / VERIFY / BLOCK│
                                        └─────────────────────────┘
```

---

## 2. System Structure: Two Interconnected Experiences

The SpendGuard application is divided into two distinct experiences:

1. **The Cinematic Landing Page (`/`)**:  
   An interactive product introduction, architectural explanation, and interactive demo that demonstrates *why* evidence-backed autonomy is essential.
2. **The Functional Console (`/console`)**:  
   The operational command center connected to the live Python/FastAPI backend, SQLite database, machine learning risk engine, and Razorpay gateway.

---

## 3. Deep Dive: Landing Page Sections (`/`)

The landing page is designed with dark navy aesthetics, editorial serif headlines (`Playfair Display`), monospace data readouts (`DM Mono`), and Framer Motion micro-interactions.

---

### Hero Section: "TRUST BEFORE THE TAP."
* **What it shows**:
  - The SpendGuard wordmark and primary navigation.
  - Large orbital line-art animation (`.trust-orbit`) representing continuous multi-signal payment surveillance.
  - Display headline: *"TRUST FOR AUTONOMOUS SPENDING."*
  - Dual CTAs: **"Open Live Console →"** (navigates to the functional console) and **"See how it works ↗"** (smooth-scrolls to the mechanics).
* **How it works**:
  - Framer Motion tracks window scroll (`scrollYProgress`) to scale and translate the orbit rings smoothly.
  - The "Open Console" button triggers state navigation to the full application.

---

### Section 01: The Problem ("AI CAN SPEND. BUT SHOULD IT?")
* **What it shows**:
  - The payment pipeline flow: `USER → AI AGENT → MERCHANT → PAYMENT`.
  - The core vulnerability callout: **"AUTHORIZED. BUT WRONG."**
* **Why it matters**:
  - Explains that legacy security models only check *if the payment card is valid*, not *whether the purchase matches the user's intent*.

---

### Section 02: How It Works & Interactive Trust Glossary ("FOUR CHECKS. ONE DECISION.")
* **What it shows**:
  - Four interactive signal rows corresponding to the 4 Trust Pillars:
    1. **`01 / AUTHORITY`**: Can the agent make this purchase? (Spending caps, recurring schedules, whitelisted merchants).
    2. **`02 / INTENT`**: Is this what the user asked for? (Hard requirements match, soft preference scoring, color/variant checks).
    3. **`03 / BEHAVIOR`**: Does the agent still behave normally? (22-feature ML model checking rolling velocity and split-payment bursts).
    4. **`04 / EVIDENCE`**: Can the product claims be proven? (Merchant catalog validation, SKU resolution, specification checks).
  - Hover / tap glossary tooltips that explain each concept in plain language.
  - A three-state decision toggle strip showing the possible outcomes: **ALLOW**, **VERIFY**, and **BLOCK**.

---

### Section 03: Live Trust Decision ("WITHIN BUDGET. WRONG PURCHASE.")
* **What it shows**:
  - A real-world scenario breakdown: User requests *"Buy me a Sony WH-1000XM6, black, under ₹35,000"*.
  - A step-by-step decision sequence:
    1. `Purchase Request` $\rightarrow$ Received
    2. `Authority` $\rightarrow$ PASS (within ₹35,000 limit)
    3. `Intent` $\rightarrow$ PASS (product family matched)
    4. `Behavior` $\rightarrow$ PASS (velocity normal)
    5. `Evidence` $\rightarrow$ **CONFLICT** (merchant model mismatch)
  - Result: **BLOCKED (EVIDENCE CONFLICT)**.
  - An interactive **"Replay decision ↻"** button that animates through each check sequentially.

---

### Section 04: Evidence & Verification ("DON'T TRUST THE CLAIM. VERIFY THE EVIDENCE.")
* **What it shows**:
  - A side-by-side comparison diagram:
    - **Agent Claim**: `RTX 4060` (8GB VRAM)
    - **Merchant Specification / Checkout SKU**: `RTX 3050` (6GB VRAM)
  - A glowing central connector indicating an **Evidence Conflict**.
  - Final badge: `EVIDENCE CONFLICT DETECTED / BLOCKED`.
* **Why it matters**:
  - Demonstrates how SpendGuard prevents agent hallucination or merchant SKU spoofing by inspecting physical catalog specifications rather than trusting agent JSON claims.

---

### Section 05: The Trust Receipt ("EVERY DECISION LEAVES PROOF.")
* **What it shows**:
  - A structured financial Trust Receipt card for transaction `#000184` (Sony XM5 substitution at ₹28,000).
  - Contains: User Intent, Selected Item, Price, Decision (`VERIFY`), 4-Pillar status grid, and plain-language rationale.
  - **"Download receipt ↓"** button: Generates an immutable, presentation-ready PDF using `jsPDF` containing the complete audit trail.

---

### Section 06: Observability ("SEE HOW THE DECISION HAPPENED.")
* **What it shows**:
  - An 8-step chronological event timeline:
    1. *Intent created* (signed with SHA-256 hash)
    2. *Search initiated*
    3. *17 products found*
    4. *9 rejected — over budget*
    5. *3 rejected — requirement mismatch*
    6. *XM6 unavailable*
    7. *XM5 selected*
    8. *Human approval requested* (placed on pre-auth hold)

---

### Section 07: Real Backend Scenario Library ("THREE OUTCOMES. ONE TRUST MODEL.")
* **What it shows**:
  - Three interactive tabs:
    - **`01 / ALLOW`**: Exact match (Sony WH-1000XM5 clean purchase at ₹29,990).
    - **`02 / VERIFY`**: Soft substitution (Requested XM6 unavailable $\rightarrow$ XM5 substitute nudged to verification hold).
    - **`03 / BLOCK`**: Evidence conflict (50mm driver claim vs 30mm physical specification).
* **Live Integration**:
  - When a tab is selected, the frontend dispatches a real `POST /transactions/evaluate` call to the FastAPI backend.
  - The four checks and the final decision badge render the **actual response returned by the backend decision engine**.

---

### Section 08: Live Metrics Strip
* **What it shows**:
  - Live aggregated counts fetched from `GET /transactions`:
    - **Trust Signals** (4 Pillars)
    - **Products Observed / Evaluations** (110 benchmark transactions)
    - **Risk Signals Rejected** (65 blocked fraud/attack attempts)
    - **Decision Trails** (110 tamper-proof hash chains)

---

### Section 09: Console Preview & Founder Note
* **What it shows**:
  - Console preview card showing `Decision / 000184` in `VERIFY` state.
  - Founder manifesto quote: *“Autonomy should never require blind faith.”*
  - **"Open SpendGuard Console →"** CTA button.

---

## 4. Deep Dive: The Operational Console (`/console`)

The Console is the full-featured application interface. It communicates directly with the FastAPI REST API.

---

### Top Navigation Bar & Global Controls
- **Wordmark & Badge**: `SPENDGUARD CONSOLE`.
- **"← Back to Product"**: Switches back to the landing page.
- **Tab Switcher**: `Overview`, `Transactions`, `Verification Queue`, `Purchase Sessions`.
- **"Seed 110 Scenarios" Button**: Calls `POST /admin/seed_scenarios` to populate the canonical benchmark dataset into SQLite.
- **Decision Engine Live Indicator**: Periodically pings `GET /health` and displays a pulsing green dot when operational.

---

### 1. Overview Tab (`/console`)
Connected to `GET /transactions`, `GET /sessions`, and `GET /escalations`.
- **Quiet Metric Strip**:
  - *Evaluations*: Total count of evaluated transactions.
  - *Protected Value*: Total INR value of blocked fraud/attacks (e.g. ₹18,56,936).
  - *Verification Holds*: Total INR value currently held in two-phase pre-auth holds.
  - *Clean Authorized*: Total INR value approved and captured immediately.
- **Real-Time 3-State Pipeline**:
  - Breakdown boxes for `01 DIRECT ALLOW`, `02 HELD FOR REVIEW`, and `03 FRAUD BLOCKED` with transaction counts and sums.
- **Pending Escalations Banner**:
  - Alerts the operator when items in the verification queue require immediate attention before their 15-minute SLA timer expires.
- **Recent Decision Activity Feed**:
  - Interactive rows showing recent transactions with merchant name, monospace amount, timestamp, agent ID, and decision pill (`ALLOW` / `VERIFY` / `BLOCK`).
  - Clicking any row opens the **Transaction Detail** investigation screen.

---

### 2. Transactions Feed Tab (`/console/transactions`)
Connected to `GET /transactions`.
- **Decision Filter Pills**: Filter instantly by `ALL`, `ALLOW`, `VERIFY`, or `BLOCK`.
- **Search Bar**: Real-time search across Transaction ID, Merchant name, Agent ID, or Category.
- **Agent Dropdown**: Filter activity to a specific agent (e.g., `agent_shopping_01`, `agent_grocery_01`).
- **Data Rows**: Monospace IDs, human-readable dates, session tags, risk scores, confidence percentages, formatted INR values, and status badges.

---

### 3. Transaction Detail / Investigation Screen (`/console/transactions/:id`)
Connected to `GET /transactions/{id}/receipt` and `GET /transactions/{id}/snapshot`.
This is the audit room for a transaction:
1. **Header & Decision Status**:
   - Transaction ID, evaluation timestamp, agent ID, and current state badge.
2. **Operator Resolution Controls (for `VERIFY` transactions)**:
   - **"Approve & Capture"** button: Calls `POST /transactions/{id}/verify` with `{"approved": true}`, capturing the Razorpay hold.
   - **"Reject & Void"** button: Calls `POST /transactions/{id}/verify` with `{"approved": false}`, voiding the hold and returning earmarked funds.
3. **Intent Fidelity Investigation Box**:
   - Left: Original User Mandate requirement (what the user asked for).
   - Right: Agent Selected Item and Amount with plain-language decision rationale.
4. **The 4-Pillar Evaluation Matrix**:
   - Four dedicated cards for Authority, Intent, Evidence, and Behavior with individual pass/fail badges, confidence scores, and specific reasons.
5. **Cryptographic Provenance Timeline**:
   - Chronological stream of SHA-256 hash-chained audit events demonstrating the agent's exact decision steps.
6. **Immutable Trust Receipt**:
   - Presentation card with an **"Export Receipt PDF"** button.

---

### 4. Verification Queue Tab (`/console/review`)
Connected to `GET /escalations`.
- Displays all transactions in `VERIFY` state with active two-phase payment holds.
- **Features per Card**:
  - Transaction ID and agent metadata.
  - Hold Amount in monospace INR.
  - **Live SLA Timer**: Displays remaining time out of the 15-minute window (`XX.Xm remaining`).
  - Plain-language explanation of why the purchase was flagged (e.g. *“Intent soft score 0.33 is below threshold (substitution)”*).
  - 1-click **"Approve & Capture Payment"** and **"Reject & Void Hold"** action buttons.
  - Reactive feedback: Immediately resolves the card, captures/voids the hold in the database, and refreshes the queue.

---

### 5. Purchase Sessions Tab (`/console/sessions`)
Connected to `GET /sessions` and `GET /sessions/{session_id}`.
- Tracks multi-step purchasing tasks (e.g. an agent buying components for an office setup across multiple transactions).
- **Features per Session**:
  - Session ID and overarching intent description.
  - Declared Total Budget vs. Cumulative Spent so far.
  - Visual Progress Bar (color-coded: green under 70%, amber 70-90%, red >90%).
  - Item quota tracking (e.g. 6 / 6 items).
  - **High Utilization / Velocity Surge Warning**: Flags when an agent approaches budget limits or executes rapid micro-burst transactions.
  - Embedded transaction stream showing every micro-purchase linked to the session.

---

## 5. How the Backend Decision Engine Works

When a transaction is submitted to `POST /transactions/evaluate`, it passes through four sequential gates:

```
                      Transaction Request
                               │
               ┌───────────────▼───────────────┐
               │     1. AUTHORITY PILLAR       │
               │  - Single tx limit            │
               │  - Daily / Period cap         │
               │  - Merchant whitelist         │
               │  - Category scope             │
               │  - Time-of-day window         │
               └───────────────┬───────────────┘
                               │
                 Passed? ──────┴────── No ──► [ BLOCK: Budget/Scope Violation ]
                               │ Yes
               ┌───────────────▼───────────────┐
               │      2. INTENT PILLAR         │
               │  - Hard requirements match    │
               │  - Weighted soft preferences  │
               │  - Goal drift vs session      │
               └───────────────┬───────────────┘
                               │
             Hard Mismatch? ───┴─── Yes ──► [ BLOCK: Wrong Product ]
                               │ No
               ┌───────────────▼───────────────┐
               │      3. BEHAVIOR PILLAR       │
               │  - 22 engineered features     │
               │  - Gradient Boosting ML model │
               │  - Rolling velocity ratio     │
               └───────────────┬───────────────┘
                               │
               Risk > 0.70? ───┴─── Yes ──► [ BLOCK: Anomaly / Split Payment ]
                               │ No
               ┌───────────────▼───────────────┐
               │      4. EVIDENCE PILLAR       │
               │  - Multi-source catalog check │
               │  - Physical spec verification │
               │  - SHA-256 hash chaining      │
               └───────────────┬───────────────┘
                               │
            Spec Conflict? ────┴─── Yes ──► [ BLOCK: Evidence Conflict ]
                               │ No
               ┌───────────────▼───────────────┐
               │    SUBSTITUTION / DRIFT?      │
               └───────────────┬───────────────┘
                               │
              Yes ─────────────┴───────────── No
               │                              │
               ▼                              ▼
     [ DECISION: VERIFY ]           [ DECISION: ALLOW ]
   - Two-phase Auth Hold          - Immediate Razorpay Order
   - 15-minute SLA Queue          - Direct Payment Capture
   - Human Operator Review        - Zero Latency
```

---

## 6. How Changes Propagate Across the System

Here is what happens when an operator or agent performs an action:

1. **Agent Submits Purchase**:
   - Agent sends `TransactionRequest` to `POST /transactions/evaluate`.
   - Backend evaluates all 4 pillars, computes risk score, logs provenance events to SQLite, and sets decision.
   - If `ALLOW`: A test order is created on Razorpay.
   - If `VERIFY`: A pre-auth hold is created in SQLite (`payment_holds`), and an escalation entry is added to `escalations`.
   - Returns a `DecisionReceipt` and seals an immutable `TrustSnapshot`.

2. **Operator Approves a Verification Hold**:
   - Operator clicks **"Approve & Capture"** in the Verification Queue or Transaction Detail.
   - Frontend sends `POST /transactions/{id}/verify` with `{"approved": true}`.
   - Backend updates decision to `ALLOW`, captures the pre-auth hold, creates a Razorpay capture order, marks the escalation as resolved, and logs an immutable audit event in `audit_log`.
   - The UI immediately transitions the badge to `APPROVED` and removes the item from the pending queue.

3. **Scenario Seeding**:
   - Clicking **"Seed 110 Scenarios"** calls `POST /admin/seed_scenarios`.
   - The backend runs all 110 benchmark scenarios (budget violations, wrong products, substitutions, split-payments, evidence conflicts, stale mandates, legitimate purchases) through the real engine and populates the SQLite database.
   - All metrics, activity feeds, and session views instantly reflect the full dataset.

---

## 7. Quick Reference: Running the System

```bash
# 1. Start the FastAPI Backend (Port 8000)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 2. Start the React Frontend (Port 3000)
cd frontend
yarn start

# 3. Run Backend Test Suite (67 tests)
PYTHONPATH=. pytest tests/ -v
```
