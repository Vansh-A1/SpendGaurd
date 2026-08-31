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
        "SPENDGUARD_API_KEY": "sg_live_your_key_here"
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
        "SPENDGUARD_API_KEY": "sg_live_production_key"
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
- **HELD FOR HUMAN REVIEW**:  
  `HELD FOR HUMAN VERIFICATION: Purchase requires human operator approval. (Hold ID: hold_abc) Reason: soft preferences mismatch (color).`
- **BLOCKED**:  
  `BLOCKED: Purchase was rejected by SpendGuard Trust Gateway. Reason: evidence conflict on hard requirement (ram_gb, storage_gb).`
- **FAIL-CLOSED ON NETWORK ERROR**:  
  `BLOCKED (SECURITY FAIL-CLOSED): SpendGuard Trust Gateway is unreachable. The transaction was blocked because corporate security policies cannot be verified offline.`
