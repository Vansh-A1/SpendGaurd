"""
SpendGuard Raw Anthropic (Claude) Tool-Calling Integration Example.

Shows how to govern a Claude agent using anthropic SDK directly (without LangChain)
by passing ANTHROPIC_TOOL_SCHEMA in client.messages.create(tools=[...]).
"""

import os
import json
from dotenv import load_dotenv

from spendguard import ANTHROPIC_TOOL_SCHEMA, execute_native_checkout, SpendGuardClient

load_dotenv()

# 1. Initialize SpendGuard Client
sg_client = SpendGuardClient(base_url="http://localhost:8000")

# 2. Native Anthropic tool array
tools = [
    ANTHROPIC_TOOL_SCHEMA,
]

# Example snippet for Anthropic client invocation:
# from anthropic import Anthropic
# client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
#
# response = client.messages.create(
#     model="claude-3-5-sonnet-20241022",
#     max_tokens=1024,
#     tools=tools,
#     messages=[
#         {"role": "user", "content": "Purchase ThinkPad T14 (SKU: TRAP-ELEC-LENOVO-T14-SPOOF) for ₹49,990 from TechDeals Direct."}
#     ]
# )
#
# for block in response.content:
#     if block.type == "tool_use" and block.name == "spendguard_checkout":
#         observation = execute_native_checkout(block.input, client=sg_client)
#         print("SpendGuard Observation:", observation)

if __name__ == "__main__":
    print("SpendGuard Anthropic Tool Schema:")
    print(json.dumps(ANTHROPIC_TOOL_SCHEMA, indent=2))
