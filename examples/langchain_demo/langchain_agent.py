"""
Standalone LangChain Shopping Agent Demo with SpendGuard AI Trust Gate Governance.

Demonstrates how any generic LangChain agent (OpenAI / Groq) is automatically
gated against adversarial traps (spec spoofing, prompt injection, split payments)
by plugging in the SpendGuardCheckoutTool.
"""

import os
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

from spendguard import SpendGuardClient, SpendGuardCheckoutTool
from simulator.catalog_server import get_trap_catalog


# ------------------------------------------------------------------------------
# 1. Standard Marketplace Catalog Tools (Search, View, Cart)
# ------------------------------------------------------------------------------

@tool
def search_catalog(query: str, max_price: Optional[float] = None) -> str:
    """Search the marketplace product catalog for items by keyword or category."""
    catalog = get_trap_catalog()
    query_terms = [t.lower() for t in query.replace(",", " ").replace("-", " ").split() if len(t) > 2]
    results = []
    for item in catalog:
        text = f"{item.get('name', '')} {item.get('brand', '')} {item.get('model', '')} {item.get('category', '')} {json.dumps(item.get('listing_claims', {}))}".lower()
        matches = sum(1 for term in query_terms if term in text) if query_terms else 1
        if matches > 0:
            if max_price is not None and float(item.get("price", 0)) > max_price * 1.5:
                continue
            results.append((matches, item))

    results.sort(key=lambda x: x[0], reverse=True)
    formatted = [
        {
            "sku": item["sku"],
            "name": item["name"],
            "brand": item.get("brand"),
            "price": item["price"],
            "merchant": item["merchant"],
        }
        for _, item in results[:5]
    ]
    if not formatted:
        formatted = [{"sku": i["sku"], "name": i["name"], "brand": i.get("brand"), "price": i["price"], "merchant": i["merchant"]} for i in catalog[:4]]
    return json.dumps(formatted, indent=2)


@tool
def view_product(sku: str) -> str:
    """Inspect complete product specifications, claimed features, seller, and price for a given SKU."""
    catalog = get_trap_catalog()
    item = next((p for p in catalog if p["sku"].upper() == sku.upper()), None)
    if not item:
        return json.dumps({"error": f"Product with SKU '{sku}' not found."})
    return json.dumps({
        "sku": item["sku"],
        "name": item["name"],
        "brand": item["brand"],
        "model": item.get("model", ""),
        "category": item.get("category", "electronics"),
        "price": item["price"],
        "merchant": item["merchant"],
        "listing_claims": item.get("listing_claims", {}),
    }, indent=2)


@tool
def add_to_cart(sku: str) -> str:
    """Add a verified product SKU to the shopping cart."""
    catalog = get_trap_catalog()
    item = next((p for p in catalog if p["sku"].upper() == sku.upper()), None)
    if not item:
        return json.dumps({"error": f"SKU {sku} not found"})
    return json.dumps({
        "status": "added_to_cart",
        "sku": sku,
        "name": item["name"],
        "price": item["price"],
    })


# ------------------------------------------------------------------------------
# 2. LangChain Agent Builder with SpendGuard Governance
# ------------------------------------------------------------------------------

def create_spendguard_langchain_agent(
    client: Optional[SpendGuardClient] = None,
    model_name: Optional[str] = None,
):
    """
    Creates a standard LangChain tool-calling procurement agent equipped with SpendGuard.
    """
    sg_client = client or SpendGuardClient(
        base_url=os.environ.get("SPENDGUARD_API_URL", "http://localhost:8000"),
        api_key=os.environ.get("SPENDGUARD_API_KEY", "sg_dev_local_key"),
    )
    checkout_tool = SpendGuardCheckoutTool(client=sg_client)
    tools = [search_catalog, view_product, add_to_cart, checkout_tool]

    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if groq_key:
        llm = ChatGroq(
            api_key=groq_key,
            model_name=model_name or os.environ.get("LLM_MODEL", "openai/gpt-oss-20b"),
            temperature=0.1,
        )
    elif openai_key:
        llm = ChatOpenAI(
            api_key=openai_key,
            model_name=model_name or "gpt-4o",
            temperature=0.1,
        )
    else:
        raise RuntimeError("No LLM API key configured in .env (GROQ_API_KEY or OPENAI_API_KEY required)")

    llm_with_tools = llm.bind_tools(tools)
    return llm_with_tools, tools


def run_langchain_procurement(
    user_prompt: str,
    budget_limit: float,
    client: Optional[SpendGuardClient] = None,
    model_name: Optional[str] = None,
    max_turns: int = 5,
) -> List[Dict[str, Any]]:
    """
    Runs a multi-turn LangChain tool-calling loop for a procurement request.
    Returns step-by-step transcript trace.
    """
    llm_with_tools, tools_list = create_spendguard_langchain_agent(client=client, model_name=model_name)
    tools_by_name = {t.name: t for t in tools_list}

    system_prompt = (
        "You are an autonomous corporate procurement assistant.\n"
        f"User Purchase Request: \"{user_prompt}\"\n"
        f"Approved Budget Ceiling: ₹{budget_limit:,.0f}\n\n"
        "EXECUTION PROTOCOL:\n"
        "1. Find candidate product with search_catalog.\n"
        "2. View candidate product details with view_product to inspect claims and seller.\n"
        "3. Add candidate to cart with add_to_cart.\n"
        "4. ALWAYS call spendguard_checkout with (sku, amount, merchant, brand, model, claimed_specs) to finalize the purchase.\n"
        "5. If spendguard_checkout returns APPROVED, inform the user with the order ID.\n"
        "6. If spendguard_checkout returns BLOCKED, explain the exact Trust Gate reason to the user."
    )

    from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Please fulfill this purchase request: {user_prompt}"),
    ]

    transcript = []

    for turn in range(max_turns):
        ai_msg: AIMessage = llm_with_tools.invoke(messages)
        messages.append(ai_msg)

        thought_text = ai_msg.content if isinstance(ai_msg.content, str) and ai_msg.content else ""
        if thought_text:
            transcript.append({
                "turn": turn + 1,
                "type": "AGENT_THOUGHT",
                "content": thought_text,
            })

        if not ai_msg.tool_calls:
            # Agent concluded reasoning
            break

        for tc in ai_msg.tool_calls:
            fn_name = tc["name"]
            fn_args = tc["args"]
            tool_obj = tools_by_name.get(fn_name)

            transcript.append({
                "turn": turn + 1,
                "type": "TOOL_CALL",
                "tool": fn_name,
                "args": fn_args,
            })

            if tool_obj:
                try:
                    observation = tool_obj.invoke(fn_args)
                except Exception as e:
                    observation = f"Tool execution error: {e}"
            else:
                observation = f"Error: Tool '{fn_name}' not found."

            transcript.append({
                "turn": turn + 1,
                "type": "TOOL_OBSERVATION",
                "tool": fn_name,
                "observation": str(observation),
            })

            messages.append(ToolMessage(
                content=str(observation),
                tool_call_id=tc["id"],
            ))

    return transcript
