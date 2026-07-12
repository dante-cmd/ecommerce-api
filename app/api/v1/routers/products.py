from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import DbDep
from app.core.permissions import get_current_user, require_admin
from app.models.user import User
from app.schemas.common import CursorPagination
from app.schemas.product import (
    CategoryCreate,
    CategoryOut,
    ProductCreate,
    ProductListItem,
    ProductOut,
    ProductReviewCreate,
    ProductReviewOut,
    ProductSearchFilters,
    ProductUpdate,
)
from app.services.product_service import ProductService

router = APIRouter()


@router.get("", response_model=CursorPagination[ProductListItem])
async def list_products(
    db: DbDep,
    q: str | None = None,
    category_id: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: int | None = Query(None, ge=1, le=5),
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    service = ProductService(db)
    filters = ProductSearchFilters(
        q=q,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        cursor=cursor,
        limit=limit,
    )
    result = await service.search_products(filters)
    return result


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: DbDep,
    current_user: User = Depends(require_admin),
):
    service = ProductService(db)
    return await service.create_category(data.name, data.slug, data.description)


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(db: DbDep):
    service = ProductService(db)
    return await service.list_categories()


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    db: DbDep,
    current_user: User = Depends(require_admin),
):
    service = ProductService(db)
    return await service.create_product(data)


@router.get("/{slug}", response_model=ProductOut)
async def get_product(slug: str, db: DbDep):
    service = ProductService(db)
    return await service.get_product_by_slug(slug)


@router.get("/{slug}/reviews", response_model=list[ProductReviewOut])
async def get_reviews(slug: str, db: DbDep):
    service = ProductService(db)
    product = await service.get_product_by_slug(slug)
    reviews = await service.get_reviews(product.id)
    return reviews


@router.post("/{product_id}/reviews", response_model=ProductReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review(
    product_id: int,
    data: ProductReviewCreate,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    service = ProductService(db)
    return await service.add_review(current_user.id, product_id, data)


@router.patch("/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    db: DbDep,
    current_user: User = Depends(require_admin),
):
    service = ProductService(db)
    return await service.update_product(product_id, data)
