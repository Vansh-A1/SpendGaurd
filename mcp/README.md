# SpendGuard Model Context Protocol (MCP) Server

Exposes SpendGuard's **Four-Pillar AI Trust Gate** directly to Claude Desktop, Cursor, Antigravity, and any MCP-compatible agent host as a native tool (`evaluate_transaction`).

---

## 1. Quick Setup & Registration

### Claude Desktop Configuration (`claude_desktop_config.json`)

On macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`  
On Linux: `~/.config/Claude/claude_desktop_config.json`  
On Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "spendguard": {
      "command": "python",
      "args": [
        "-m",
        "spendguard.integrations.mcp_server"
      ],
      "env": {
        "SPENDGUARD_API_URL": "http://localhost:8000",
        "SPENDGUARD_API_KEY": "<your-spendguard-api-key>"
      }
    }
  }
}
```

### Cursor IDE MCP Configuration (`.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "spendguard-trust-gate": {
      "command": "python -m spendguard.integrations.mcp_server",
      "env": {
        "SPENDGUARD_API_URL": "https://spendguard.internal.net",
        "SPENDGUARD_API_KEY": "<your-spendguard-api-key>"
      }
    }
  }
}
```

---

## 2. Tool Reference: `evaluate_transaction`

Evaluates any autonomous corporate purchase against corporate mandates, intent fidelity, evidence verification, and behavioral risk gates.

### Tool Input Schema:
```json
{
  "sku": "TRAP-ELEC-DELL-5530-CLEAN",
  "amount": 48990.0,
  "merchant": "Dell Official Store",
  "category": "electronics",
  "brand": "Dell",
  "model": "Inspiron 15 5530",
  "claimed_specs": {
    "ram_gb": 16,
    "storage_gb": 512,
    "cpu": "Intel Core i5-1335U"
  }
}
```

### Natural Language Tool Observation Outputs:
- **APPROVED**:  
  `APPROVED: Purchase of TRAP-ELEC-DELL-5530-CLEAN for ₹48,990.00 at Dell Official Store authorized by SpendGuard Trust Gateway. Razorpay Order ID: order_test_123. All 4 trust pillars passed.`  
  `Summary: Approved purchase of Dell Inspiron 15 5530 (SKU: TRAP-ELEC-DELL-5530-CLEAN) from Dell Official Store for ₹48,990.00. The transaction satisfied all corporate policy limits, passed independent catalog spec verification, matched the user's requirements, and demonstrated low behavioral risk (score: 0.03). You may inform the user the purchase succeeded.`
- **HELD FOR HUMAN REVIEW**:  
  `HELD FOR HUMAN VERIFICATION: Purchase requires human operator approval. (Hold ID: hold_abc) Reason: soft preferences mismatch (color).`  
  `Summary: Held for human review: An alternative variant for Bose QuietComfort 45 from Bose Authorized Hub (₹24,900.00) was selected that differs on color, but satisfies core mandatory requirements and budget caps. An operator should confirm whether this substitution is acceptable.`
- **BLOCKED**:  
  `BLOCKED: Purchase was rejected by SpendGuard Trust Gateway. Reason: blocked: evidence conflict on hard requirement (ram_gb, storage_gb).`  
  `Summary: Purchase rejected by Pillar 3 (Evidence Verification): Independent catalog verification detected a specification conflict with the seller's claims: ram_gb mismatch (claimed '32' vs actual '8'); storage_gb mismatch (claimed '1024' vs actual '256'). You must select a compliant alternative product that satisfies corporate policies or abort.`
- **FAIL-CLOSED ON NETWORK ERROR**:  
  `BLOCKED (SECURITY FAIL-CLOSED): SpendGuard Trust Gateway is unreachable. The transaction was blocked because corporate security policies cannot be verified offline.`
