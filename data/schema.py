from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


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
    model_config = {"extra": "forbid"}

    id: str = Field(max_length=128)
    agent_id: str = Field(max_length=128)
    mandate_id: str = Field(max_length=128)
    user_intent_id: str = Field(max_length=128)
    claimed_product: dict
    actual_sku: str = Field(max_length=128)
    amount: float = Field(gt=0, le=100_000_000, description="Transaction amount in INR")
    category: str = Field(max_length=128)
    merchant: str = Field(max_length=512)
    timestamp: Optional[datetime] = None
    scenario_type: str = Field(default="production", max_length=128)
    expected_decision: Optional[Literal["ALLOW", "VERIFY", "BLOCK"]] = "ALLOW"
    session_id: Optional[str] = Field(default=None, max_length=128)
    intent_version: int = 1

    @field_validator("amount")
    @classmethod
    def validate_amount_precision(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Amount must be strictly positive (> 0).")
        # Round to 2 decimal places for financial safety
        return round(float(v), 2)

    def __init__(self, **data):
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.now()
        super().__init__(**data)
