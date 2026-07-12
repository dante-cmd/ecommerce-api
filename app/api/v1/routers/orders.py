from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import DbDep
from app.core.permissions import get_current_user, require_staff_or_admin
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.order import OrderCreate, OrderListItem, OrderOut, OrderStatusUpdate
from app.services.order_service import OrderService

router = APIRouter()


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    service = OrderService(db)
    return await service.create_order(current_user.id, data)


@router.get("", response_model=list[OrderListItem])
async def list_orders(
    db: DbDep,
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    service = OrderService(db)
    return await service.list_user_orders(current_user.id, limit, offset)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    service = OrderService(db)
    return await service.get_order(current_user.id, order_id)


@router.patch("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    db: DbDep,
    current_user: User = Depends(get_current_user),
):
    service = OrderService(db)
    return await service.cancel_order(current_user.id, order_id)


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    db: DbDep,
    current_user: User = Depends(require_staff_or_admin),
):
    service = OrderService(db)
    return await service.update_status(order_id, data, is_admin=True)
