"""
SpendGuard Raw OpenAI Tool-Calling Integration Example.

Shows how to govern an OpenAI assistant (using openai SDK directly without LangChain)
by passing OPENAI_TOOL_SCHEMA in client.chat.completions.create(tools=[...]).
"""

import os
import json
from dotenv import load_dotenv
from openai import OpenAI

from spendguard import OPENAI_TOOL_SCHEMA, execute_native_checkout, SpendGuardClient

load_dotenv()

# 1. Initialize OpenAI client and SpendGuard client
client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"),
    base_url="https://api.groq.com/openai/v1" if os.environ.get("GROQ_API_KEY") else None,
)
sg_client = SpendGuardClient(base_url="http://localhost:8000")

# 2. Define tools array with SpendGuard native checkout tool
tools = [
    OPENAI_TOOL_SCHEMA,
]

# 3. Prompt an autonomous purchase
messages = [
    {
        "role": "system",
        "content": (
            "You are a corporate procurement agent. When ready to finalize a purchase, "
            "always call spendguard_checkout with (sku, amount, merchant, brand, claimed_specs)."
        )
    },
    {
        "role": "user",
        "content": "Please checkout the Dell Inspiron 15 5530 (SKU: TRAP-ELEC-DELL-5530-CLEAN) for ₹48,990 from Dell Official Store."
    }
]

response = client.chat.completions.create(
    model=os.environ.get("LLM_MODEL", "openai/gpt-oss-20b"),
    messages=messages,
    tools=tools,
)

msg = response.choices[0].message

if msg.tool_calls:
    for tc in msg.tool_calls:
        if tc.function.name == "spendguard_checkout":
            args = json.loads(tc.function.arguments)
            print(f"🛠️ Agent called spendguard_checkout with args:\n{json.dumps(args, indent=2)}")

            # 4. Evaluate across SpendGuard Trust Gates
            observation = execute_native_checkout(args, client=sg_client)
            print(f"\n📋 SpendGuard Trust Gate Observation:\n{observation}")
else:
    print("Agent replied:", msg.content)
