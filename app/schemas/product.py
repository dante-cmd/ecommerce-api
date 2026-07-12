from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    parent_id: int | None = None
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    parent_id: int | None = None
    is_active: bool | None = None


class CategoryOut(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class ProductVariantBase(BaseModel):
    sku: str
    size: str | None = None
    color: str | None = None
    price_adjustment: Decimal = Decimal("0.00")
    stock_quantity: int = Field(..., ge=0)
    is_active: bool = True


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(BaseModel):
    sku: str | None = None
    size: str | None = None
    color: str | None = None
    price_adjustment: Decimal | None = None
    stock_quantity: int | None = Field(None, ge=0)
    is_active: bool | None = None


class ProductVariantOut(ProductVariantBase):
    id: int
    product_id: int

    model_config = ConfigDict(from_attributes=True)


class ProductImageBase(BaseModel):
    url: str
    is_primary: bool = False
    order: int = 0


class ProductImageOut(ProductImageBase):
    id: int
    product_id: int

    model_config = ConfigDict(from_attributes=True)


class ProductBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    category_id: int
    base_price: Decimal = Field(..., ge=0)
    is_active: bool = True


class ProductCreate(ProductBase):
    variants: list[ProductVariantCreate] = []
    images: list[ProductImageBase] = []


class ProductUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    category_id: int | None = None
    base_price: Decimal | None = Field(None, ge=0)
    is_active: bool | None = None


class ProductOut(ProductBase):
    id: int
    rating_average: Decimal
    rating_count: int
    category: CategoryOut
    variants: list[ProductVariantOut]
    images: list[ProductImageOut]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductListItem(BaseModel):
    id: int
    name: str
    slug: str
    base_price: Decimal
    rating_average: Decimal
    rating_count: int
    category: CategoryOut
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None


class ProductReviewOut(BaseModel):
    id: int
    product_id: int
    user_id: int
    rating: int
    comment: str | None = None
    is_verified_purchase: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductSearchFilters(BaseModel):
    q: str | None = None
    category_id: int | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_rating: int | None = Field(None, ge=1, le=5)
    cursor: str | None = None
    limit: int = Field(20, ge=1, le=100)
