"""
Demonstration of SpendGuard MCP Server Tool Execution.
Directly executes evaluate_transaction tool on the SpendGuard MCPServer instance across 3 key scenarios.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient
import api.main as api_mod
from spendguard import SpendGuardClient
from spendguard.integrations.mcp_server import create_mcp_server


def create_in_process_spendguard_client():
    test_client = TestClient(api_mod.app)
    sg_client = SpendGuardClient(base_url="http://in-process-spendguard.local")

    def mock_urlopen(req, timeout=10.0):
        url = req.full_url
        path = url.replace("http://in-process-spendguard.local", "")
        method = req.get_method()
        headers = dict(req.headers)
        data_bytes = req.data
        json_data = json.loads(data_bytes.decode("utf-8")) if data_bytes else None

        if method == "POST" and path == "/transactions/evaluate":
            resp = test_client.post("/transactions/evaluate", json=json_data)
        elif method == "GET" and path == "/health":
            resp = test_client.get("/health")
        else:
            resp = test_client.get(path)

        mock_resp = MagicMock()
        mock_resp.getcode.return_value = resp.status_code
        mock_resp.read.return_value = resp.content
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    return sg_client, mock_urlopen


async def main():
    print("=" * 100)
    print(" SPENDGUARD MODEL CONTEXT PROTOCOL (MCP) EVALUATION DEMO")
    print(" Demonstrating real-time trust gating via the MCP evaluate_transaction tool")
    print("=" * 100)

    # Clear memory cache
    api_mod.MANDATES_CACHE = {}
    api_mod.CATALOG_CACHE = []

    sg_client, mock_urlopen = create_in_process_spendguard_client()
    server = create_mcp_server(client=sg_client)

    scenarios = [
        {
            "name": "Scenario 1: Clean Baseline Purchase (Dell Inspiron 15)",
            "args": {
                "sku": "TRAP-ELEC-DELL-5530-CLEAN",
                "amount": 48990.0,
                "merchant": "Dell Official Store",
                "brand": "Dell",
                "model": "Inspiron 15 5530",
                "category": "electronics",
                "claimed_specs": {"ram_gb": 16, "storage_gb": 512, "cpu": "Intel Core i5-1335U", "display_inch": 15.6, "color": "platinum silver"},
            },
            "expected": "APPROVED (All 4 Pillars Pass)",
        },
        {
            "name": "Scenario 2: Spec Spoofing Adversarial Trap (ThinkPad T14 Spoof)",
            "args": {
                "sku": "TRAP-ELEC-LENOVO-T14-SPOOF",
                "amount": 49990.0,
                "merchant": "TechDeals Direct",
                "brand": "Lenovo",
                "model": "ThinkPad T14 Gen 4",
                "category": "electronics",
                "claimed_specs": {"ram_gb": 32, "storage_gb": 1024, "cpu": "Intel Core i7-1365U", "gpu": "Dedicated Iris Xe"},
            },
            "expected": "BLOCKED (Evidence Hardware Spec Conflict)",
        },
        {
            "name": "Scenario 3: Deceptive Split Payment Token Trap (RTX 4060 Token 1 of 3)",
            "args": {
                "sku": "TRAP-ELEC-RTX4060-SPLIT-01",
                "amount": 9999.0,
                "merchant": "GPU Express Hub",
                "brand": "NVIDIA",
                "model": "GeForce RTX 4060",
                "category": "electronics",
                "claimed_specs": {"chip": "AD107", "vram_gb": 8},
            },
            "expected": "BLOCKED (Deceptive Installment Token)",
        },
    ]

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        for idx, sc in enumerate(scenarios, 1):
            print("\n" + "#" * 100)
            print(f" [{idx}/3] {sc['name']}")
            print(f" MCP Tool Arguments:\n{json.dumps(sc['args'], indent=2)}")
            print(f" Expected Outcome: {sc['expected']}")
            print("#" * 100)

            res = await server.call_tool("evaluate_transaction", sc["args"])
            observation = res.content[0].text

            print(f"\n📋 MCP Tool Observation:\n{observation}")
            print("-" * 100)


if __name__ == "__main__":
    asyncio.run(main())
