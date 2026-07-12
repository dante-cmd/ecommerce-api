from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product import ProductVariantOut


class CartItemCreate(BaseModel):
    variant_id: int
    quantity: int = Field(..., ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=0)


class CartItemOut(BaseModel):
    id: int
    variant: ProductVariantOut
    quantity: int
    unit_price: Decimal
    total_price: Decimal

    model_config = ConfigDict(from_attributes=True)


class CartOut(BaseModel):
    id: int
    items: list[CartItemOut]
    subtotal: Decimal
    item_count: int

    model_config = ConfigDict(from_attributes=True)
