import uuid
from decimal import Decimal

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.order import Order
from app.models.payment import Payment
from app.repositories.order_repository import OrderRepository
from app.repositories.payment_repository import PaymentRepository
from app.repositories.user_repository import UserRepository
from app.schemas.payment import PaymentIntentOut
from app.tasks.email_tasks import send_order_status_email


class PaymentService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.order_repo = OrderRepository(session)
        self.payment_repo = PaymentRepository(session)
        self.user_repo = UserRepository(session)
        stripe.api_key = settings.stripe_secret_key

    async def _get_user_email(self, user_id: int) -> str:
        user = await self.user_repo.get_by_id(user_id)
        return user.email if user else "customer@example.com"

    async def create_payment_intent(self, order_id: int, user_id: int) -> PaymentIntentOut:
        order = await self.order_repo.get_by_id_with_items(order_id)
        if not order:
            raise NotFoundException("Order not found")
        if order.user_id != user_id:
            raise ValidationException("Order does not belong to user")
        if order.status != "pending":
            raise ValidationException("Order is not payable")

        existing = await self.payment_repo.get_by_order_id(order_id)
        if existing and existing.provider_payment_id:
            try:
                intent = stripe.PaymentIntent.retrieve(existing.provider_payment_id)
                return PaymentIntentOut(
                    client_secret=intent.client_secret,
                    payment_intent_id=intent.id,
                    amount=order.total,
                    currency=existing.currency,
                )
            except stripe.error.StripeError as exc:
                raise ValidationException(f"Stripe error: {exc.user_message or str(exc)}") from exc

        idempotency_key = str(uuid.uuid4())
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(order.total * 100),
                currency="usd",
                metadata={"order_id": str(order.id), "user_id": str(user_id)},
                idempotency_key=idempotency_key,
            )
        except stripe.error.StripeError as exc:
            raise ValidationException(f"Stripe error: {exc.user_message or str(exc)}") from exc

        payment = Payment(
            order_id=order.id,
            provider="stripe",
            status="pending",
            amount=order.total,
            currency="usd",
            provider_payment_id=intent.id,
            idempotency_key=idempotency_key,
        )
        await self.payment_repo.create(payment)

        return PaymentIntentOut(
            client_secret=intent.client_secret,
            payment_intent_id=intent.id,
            amount=order.total,
            currency="usd",
        )

    async def handle_webhook(self, payload: bytes, signature: str) -> Payment | None:
        if not self.settings.stripe_webhook_secret:
            raise ValidationException("Webhook secret not configured")

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.settings.stripe_webhook_secret
            )
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise ValidationException("Invalid webhook signature") from exc

        if event["type"] == "payment_intent.succeeded":
            intent = event["data"]["object"]
            return await self._mark_paid(intent["id"])
        elif event["type"] in {"payment_intent.payment_failed", "charge.failed"}:
            intent = event["data"]["object"]
            return await self._mark_failed(intent.get("id"), intent.get("last_payment_error", {}).get("message"))

        return None

    async def _mark_paid(self, provider_payment_id: str) -> Payment:
        payment = await self.payment_repo.get_by_provider_payment_id(provider_payment_id)
        if not payment:
            raise NotFoundException("Payment not found")
        if payment.status == "succeeded":
            return payment

        payment.status = "succeeded"
        await self.payment_repo.update(payment)

        order = await self.order_repo.get_by_id_with_items(payment.order_id)
        if order and order.status == "pending":
            order.status = "paid"
            await self.order_repo.update(order)
            user_email = await self._get_user_email(order.user_id)
            send_order_status_email.delay(order.id, order.status, user_email)

        return payment

    async def _mark_failed(self, provider_payment_id: str | None, message: str | None) -> Payment:
        if not provider_payment_id:
            raise ValidationException("Missing payment intent id")
        payment = await self.payment_repo.get_by_provider_payment_id(provider_payment_id)
        if not payment:
            raise NotFoundException("Payment not found")
        payment.status = "failed"
        payment.failure_message = message
        await self.payment_repo.update(payment)
        return payment

    async def refund_payment(self, order_id: int, amount: Decimal | None = None) -> Payment:
        payment = await self.payment_repo.get_by_order_id(order_id)
        if not payment or payment.status != "succeeded":
            raise ValidationException("Payment not eligible for refund")

        try:
            refund = stripe.Refund.create(
                payment_intent=payment.provider_payment_id,
                amount=int(amount * 100) if amount else None,
            )
        except stripe.error.StripeError as exc:
            raise ValidationException(f"Stripe error: {exc.user_message or str(exc)}") from exc

        payment.status = "refunded"
        await self.payment_repo.update(payment)

        order = await self.order_repo.get_by_id_with_items(payment.order_id)
        if order:
            order.status = "refunded"
            await self.order_repo.update(order)
            user_email = await self._get_user_email(order.user_id)
            send_order_status_email.delay(order.id, order.status, user_email)

        return payment
