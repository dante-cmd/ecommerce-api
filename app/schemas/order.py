from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    variant_id: int | None
    product_name: str
    variant_name: str | None
    unit_price: Decimal
    quantity: int
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    shipping_address_id: int
    coupon_code: str | None = None
    notes: str | None = None


class OrderOut(BaseModel):
    id: int
    user_id: int
    status: str
    shipping_address: str
    subtotal: Decimal
    shipping_cost: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total: Decimal
    coupon_code: str | None
    notes: str | None
    items: list[OrderItemOut]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|paid|processing|shipped|delivered|cancelled|refunded)$")


class OrderListItem(BaseModel):
    id: int
    status: str
    total: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
