from datetime import datetime
from typing import Literal
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
