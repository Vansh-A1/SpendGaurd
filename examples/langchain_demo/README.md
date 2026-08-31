# SpendGuard LangChain Integration Demo

This demo illustrates how to govern a generic **LangChain tool-calling agent** using SpendGuard's `SpendGuardCheckoutTool`.

## Architecture

```
LangChain Agent (ChatGroq / ChatOpenAI)
   │
   ├── search_catalog() ───► Marketplace Catalog
   ├── view_product()   ───► Product Claims
   ├── add_to_cart()    ───► Local Cart State
   └── spendguard_checkout() ──► SpendGuard AI Trust Gateway (4 Pillars)
                                      │
                                      ├── Authority Pillar (Mandates & Caps)
                                      ├── Intent Fidelity Pillar (Specs & Brand)
                                      ├── Evidence Pillar (Barcode & Truth Verification)
                                      └── Behavioral Risk (ML Velocities & Nudges)
```

## Running the Demo

Make sure your SpendGuard backend is running (or test client configured) and `.env` has your API key:

```bash
python examples/langchain_demo/run_demo.py
```
