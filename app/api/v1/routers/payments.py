from fastapi import APIRouter, Depends, Header, Request, status

from app.api.v1.deps import DbDep, SettingsDep
from app.core.permissions import get_current_user, require_admin
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.payment import PaymentIntentOut, PaymentIntentRequest, RefundRequest
from app.services.payment_service import PaymentService

router = APIRouter()


@router.post("/intent", response_model=PaymentIntentOut)
async def create_payment_intent(
    data: PaymentIntentRequest,
    db: DbDep,
    settings: SettingsDep,
    current_user: User = Depends(get_current_user),
):
    service = PaymentService(db, settings)
    return await service.create_payment_intent(data.order_id, current_user.id)


@router.post("/webhook", response_model=MessageResponse, include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: DbDep,
    settings: SettingsDep,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
):
    payload = await request.body()
    service = PaymentService(db, settings)
    await service.handle_webhook(payload, stripe_signature)
    return MessageResponse(message="Webhook processed")


@router.post("/orders/{order_id}/refund", response_model=MessageResponse)
async def refund_order(
    order_id: int,
    data: RefundRequest,
    db: DbDep,
    settings: SettingsDep,
    current_user: User = Depends(require_admin),
):
    service = PaymentService(db, settings)
    await service.refund_payment(order_id, data.amount)
    return MessageResponse(message="Refund processed")
