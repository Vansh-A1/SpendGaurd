from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class Agent(BaseModel):
    id: str
    type: Literal["shopping", "travel", "grocery", "software"]
    name: str
    created_at: datetime


class Product(BaseModel):
    sku: str
    brand: str
    model: str
    category: str
    price: float
    specs: dict


class PurchaseSession(BaseModel):
    session_id: str
    intent_id: str
    agent_id: str
    declared_item_count: Optional[int] = None
    declared_total_budget: Optional[float] = None
    created_at: datetime


class TransactionRequest(BaseModel):
    id: str
    agent_id: str
    mandate_id: str
    user_intent_id: str
    claimed_product: dict
    actual_sku: str
    amount: float
    category: str
    merchant: str
    timestamp: datetime
    scenario_type: str
    expected_decision: Literal["ALLOW", "VERIFY", "BLOCK"]
    session_id: Optional[str] = None
    intent_version: int = 1
