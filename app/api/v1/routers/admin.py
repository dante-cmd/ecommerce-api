from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import DbDep
from app.core.permissions import require_admin, require_staff_or_admin
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.order import OrderOut
from app.schemas.product import ProductVariantUpdate
from app.services.dashboard_service import DashboardService
from app.services.order_service import OrderService
from app.services.product_service import ProductService

router = APIRouter()


@router.get("/orders", response_model=list[OrderOut])
async def list_all_orders(
    db: DbDep,
    current_user: User = Depends(require_staff_or_admin),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    service = OrderService(db)
    return await service.order_repo.list_all(limit, offset, status_filter)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order_admin(
    order_id: int,
    db: DbDep,
    current_user: User = Depends(require_staff_or_admin),
):
    service = OrderService(db)
    return await service.get_order(0, order_id, is_admin=True)


@router.patch("/variants/{variant_id}", response_model=MessageResponse)
async def update_variant_stock(
    variant_id: int,
    data: ProductVariantUpdate,
    db: DbDep,
    current_user: User = Depends(require_admin),
):
    service = ProductService(db)
    await service.update_variant(variant_id, data)
    return MessageResponse(message="Variant updated")


@router.get("/dashboard/sales")
async def dashboard_sales(
    db: DbDep,
    current_user: User = Depends(require_admin),
):
    service = DashboardService(db)
    summary = await service.get_sales_summary()
    top_products = await service.get_top_products()
    low_stock = await service.get_low_stock_count()
    return {
        "total_sales": summary["total_sales"],
        "total_orders": summary["total_orders"],
        "top_products": top_products,
        "low_stock_count": low_stock,
    }
