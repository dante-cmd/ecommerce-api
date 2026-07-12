from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PaymentIntentRequest(BaseModel):
    order_id: int


class PaymentIntentOut(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: Decimal
    currency: str

    model_config = ConfigDict(from_attributes=True)


class PaymentOut(BaseModel):
    id: int
    order_id: int
    status: str
    amount: Decimal
    currency: str
    provider_payment_id: str | None
    failure_message: str | None

    model_config = ConfigDict(from_attributes=True)


class RefundRequest(BaseModel):
    amount: Decimal | None = None
    reason: str | None = None
