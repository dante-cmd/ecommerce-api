"""Simulate a complete client interaction with the e-commerce API.

This script exercises the service layer to:

1. Register a new customer.
2. Simulate the user receiving and clicking the verification email.
3. Log the customer in.
4. Create a shipping address.
5. Add products to the cart.
6. Create an order.
7. Simulate a Stripe payment intent and webhook success.
8. Simulate the order fulfillment lifecycle (processing -> shipped -> delivered).

All emails that would normally be sent by Celery are captured and saved to
``app/scripts/mailbox/`` instead of being delivered over SMTP.  Stripe calls
are mocked so the simulation runs without real API keys.

Run with:

    python -m app.scripts.simulate_client

Make sure the database is migrated and reachable through ``DATABASE_URL``.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# fmt: off
_STREETS = [
    "123 Main St", "456 Oak Avenue", "789 Pine Road", "101 Maple Blvd",
    "202 Elm Street", "303 Cedar Lane", "404 Birch Way", "505 Spruce Drive",
    "606 Willow Court", "707 Aspen Circle", "808 Redwood Terrace",
    "909 Magnolia Avenue", "111 Cherry Lane", "222 Peach Street",
    "333 Plum Road", "444 Walnut Blvd", "445 Chestnut Drive",
    "556 Hickory Way", "667 Poplar Court", "778 Dogwood Circle",
]
_CITIES = [
    ("Springfield", "IL", "62701"), ("Austin", "TX", "73301"),
    ("Denver", "CO", "80201"), ("Seattle", "WA", "98101"),
    ("Boston", "MA", "02101"), ("Miami", "FL", "33101"),
    ("Atlanta", "GA", "30301"), ("Phoenix", "AZ", "85001"),
    ("Portland", "OR", "97201"), ("Nashville", "TN", "37201"),
]
# fmt: on

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.core.security import create_email_token
from app.models import Category, Product, ProductVariant
from app.schemas.cart import CartItemCreate
from app.schemas.order import OrderCreate, OrderStatusUpdate
from app.schemas.user import AddressCreate, UserCreate, UserLogin
from app.services.auth_service import AuthService
from app.services.cart_service import CartService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.user_service import UserService
from app.tasks import email_tasks


class FakeRedis:
    """Minimal async Redis stand-in for AuthService.

    Refresh-token blacklisting is not exercised by the simulation, so the
    implementation is intentionally no-op.
    """

    async def get(self, key: str) -> None:  # noqa: ARG002
        return None

    async def setex(self, key: str, seconds: int, value: str) -> None:  # noqa: ARG002
        return None


class Mailbox:
    """Collects rendered emails as if they landed in a user's inbox."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.emails: list[dict[str, Any]] = []

    def deliver(self, message: Any) -> None:
        """Save a FastMail ``MessageSchema`` to disk and record metadata."""
        index = len(self.emails)
        timestamp = datetime.now().isoformat()
        filename = f"{index:03d}_{timestamp.replace(':', '-')}.html"
        path = self.directory / filename
        body = getattr(message, "body", None) or "<no body>"
        path.write_text(str(body), encoding="utf-8")

        info = {
            "to": list(getattr(message, "recipients", [])),
            "subject": getattr(message, "subject", "<no subject>"),
            "path": str(path),
        }
        self.emails.append(info)
        print(f"  📧 {info['subject']} -> {info['to']} (saved to {path.name})")


class FakePaymentIntent:
    """Stripe PaymentIntent look-alike returned by our mock."""

    def __init__(self, amount: int, currency: str, metadata: dict[str, str]) -> None:
        self.id = f"pi_sim_{uuid.uuid4().hex[:16]}"
        self.client_secret = f"{self.id}_secret_sim"
        self.amount = amount
        self.currency = currency
        self.metadata = metadata


def fake_payment_intent_create(
    *, amount: int, currency: str, metadata: dict[str, str], idempotency_key: str, **kwargs: Any
) -> FakePaymentIntent:
    """Mock ``stripe.PaymentIntent.create`` so no real Stripe call is made."""
    print(f"  💳 [Stripe mock] PaymentIntent.create amount={amount} {currency}")
    return FakePaymentIntent(amount=amount, currency=currency, metadata=metadata)


def fake_payment_intent_retrieve(payment_intent_id: str, **kwargs: Any) -> FakePaymentIntent:
    """Mock ``stripe.PaymentIntent.retrieve``."""
    intent = FakePaymentIntent(amount=0, currency="usd", metadata={})
    intent.id = payment_intent_id
    intent.client_secret = f"{payment_intent_id}_secret_sim"
    return intent


async def ensure_sample_products(session: AsyncSession) -> list[int]:
    """Return active variant ids, creating sample products if the DB is empty."""
    result = await session.execute(
        select(ProductVariant).where(ProductVariant.is_active.is_(True))
    )
    variants = list(result.scalars().all())
    if variants:
        return [variant.id for variant in variants]

    print("No product variants found; creating sample data for the simulation...")
    category = Category(name="Simulation", slug="simulation", description="Sample category")
    session.add(category)
    await session.flush()

    product = Product(
        name="Demo Product",
        slug="demo-product",
        description="A sample product used by the client simulation.",
        category_id=category.id,
        base_price=Decimal("49.99"),
    )
    session.add(product)
    await session.flush()

    variant_a = ProductVariant(
        product_id=product.id,
        sku="DEMO-001-BLK",
        color="Black",
        stock_quantity=100,
    )
    variant_b = ProductVariant(
        product_id=product.id,
        sku="DEMO-002-WHT",
        color="White",
        stock_quantity=100,
    )
    session.add_all([variant_a, variant_b])
    await session.flush()

    return [variant_a.id, variant_b.id]


async def restock_variant(session: AsyncSession, variant_id: int, min_stock: int = 50) -> None:
    """Ensure a variant has at least ``min_stock`` units available."""
    result = await session.execute(
        select(ProductVariant).where(ProductVariant.id == variant_id)
    )
    variant = result.scalar_one_or_none()
    if variant is None:
        raise RuntimeError(f"Variant {variant_id} not found")

    if variant.stock_quantity < min_stock:
        restock_amount = min_stock - variant.stock_quantity
        variant.stock_quantity = min_stock
        await session.flush()
        print(f"   Restocked {variant.sku} (+{restock_amount}) to {min_stock}")


async def pick_variants(session: AsyncSession, count: int = 2) -> list[int]:
    """Return ``count`` random active variant ids, restocking them if necessary."""
    result = await session.execute(
        select(ProductVariant).where(ProductVariant.is_active.is_(True))
    )
    variants = list(result.scalars().all())
    if len(variants) < count:
        raise RuntimeError(f"Not enough active variants (found {len(variants)}, need {count})")

    selected = random.sample(variants, count)
    for variant in selected:
        await restock_variant(session, variant.id, min_stock=50)

    return [variant.id for variant in selected]


async def simulate(settings: Settings, mailbox_dir: Path) -> None:
    """Run the complete client interaction."""
    mailbox = Mailbox(mailbox_dir)

    # Capture rendered emails instead of sending them over SMTP.
    original_send = email_tasks._send
    email_tasks._send = lambda message: mailbox.deliver(message)

    # Replace Stripe network calls with deterministic mocks.
    original_stripe_create = stripe.PaymentIntent.create
    original_stripe_retrieve = stripe.PaymentIntent.retrieve
    stripe.PaymentIntent.create = fake_payment_intent_create
    stripe.PaymentIntent.retrieve = fake_payment_intent_retrieve

    # Run Celery email tasks synchronously so the mailbox patch catches them.
    from app.tasks.celery_app import celery_app

    original_always_eager = celery_app.conf.task_always_eager
    celery_app.conf.task_always_eager = True

    engine = create_async_engine(str(settings.database_url), echo=settings.debug, future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with SessionLocal() as session:
            variant_ids = await pick_variants(session, count=2)

            # Services
            fake_redis = FakeRedis()
            auth_service = AuthService(session, settings, fake_redis)
            user_service = UserService(session)
            cart_service = CartService(session)
            order_service = OrderService(session)
            payment_service = PaymentService(session, settings)

            # 0. Sometimes simulate an abandoned guest cart to populate session_id rows
            if random.random() < 0.4:
                session_id = f"sim_session_{uuid.uuid4().hex[:16]}"
                print(f"\n0) Creating abandoned guest cart (session_id={session_id})...")
                guest_variant_ids = await pick_variants(session, count=2)
                for variant_id in guest_variant_ids:
                    await cart_service.add_item(
                        CartItemCreate(variant_id=variant_id, quantity=random.randint(1, 2)),
                        session_id=session_id,
                    )
                print("   Guest cart items added (not checked out)")

            # 1. Register
            user_email = f"sim.client.{uuid.uuid4().hex[:8]}@example.com"
            password = "Password123!"
            print(f"\n1) Registering customer {user_email}...")
            user = await auth_service.register(
                UserCreate(
                    email=user_email,
                    password=password,
                    first_name="Sim",
                    last_name="Client",
                    phone="+1 555 0100",
                )
            )
            print(f"   User created: id={user.id}")

            # 2. Verify email (simulate user clicking the link in their inbox)
            print("\n2) Simulating email verification...")
            token = create_email_token(user.id, settings)
            await auth_service.verify_email(token)
            print(f"   Email verified: is_verified={user.is_verified}")

            # 3. Login
            print("\n3) Logging in...")
            tokens = await auth_service.login(UserLogin(email=user_email, password=password))
            print(f"   Access token: {tokens.access_token[:20]}...")

            # 4. Create shipping address
            print("\n4) Creating shipping address...")
            city, state, postal_code = random.choice(_CITIES)
            address = await user_service.create_address(
                user.id,
                AddressCreate(
                    label=random.choice(["Home", "Work", "Apartment"]),
                    street=random.choice(_STREETS),
                    city=city,
                    state=state,
                    postal_code=postal_code,
                    country="US",
                    is_default=True,
                ),
            )
            print(f"   Address: {address.street}, {address.city}, {address.state} {address.postal_code}")

            # 5. Add items to cart
            print("\n5) Adding items to cart...")
            quantities = [random.randint(1, 3) for _ in variant_ids]
            for variant_id, quantity in zip(variant_ids, quantities):
                cart = await cart_service.add_item(
                    CartItemCreate(variant_id=variant_id, quantity=quantity),
                    user_id=user.id,
                )
            print(f"   Cart items: {sum(item.quantity for item in cart.items)}")

            # 6. Create order
            print("\n6) Creating order...")
            order = await order_service.create_order(
                user.id,
                OrderCreate(
                    shipping_address_id=address.id,
                    notes="Please leave the package at the front door.",
                ),
            )
            print(f"   Order #{order.id}: total=${order.total}, status={order.status}")

            # 7. Payment intent (Stripe mock)
            print("\n7) Creating payment intent...")
            intent = await payment_service.create_payment_intent(order.id, user.id)
            print(f"   Payment intent: {intent.payment_intent_id}")

            # 8. Simulate Stripe webhook: payment_intent.succeeded
            print("\n8) Verifying payment (simulating Stripe webhook)...")
            payment = await payment_service._mark_paid(intent.payment_intent_id)
            order = await order_service.get_order(user.id, order.id, is_admin=True)
            print(f"   Payment status: {payment.status}")
            print(f"   Order status: {order.status}")

            # 9. Fulfillment lifecycle (admin updates)
            print("\n9) Simulating order fulfillment...")
            for status in ("processing", "shipped", "delivered"):
                order = await order_service.update_status(
                    order.id,
                    OrderStatusUpdate(status=status),
                    is_admin=True,
                )
                print(f"   Order status: {order.status}")

            await session.commit()

        # Summary
        print("\n" + "=" * 50)
        print("SIMULATION COMPLETE")
        print("=" * 50)
        print(f"Customer:     {user.email}")
        print(f"Order ID:     {order.id}")
        print(f"Subtotal:     ${order.subtotal}")
        print(f"Shipping:     ${order.shipping_cost}")
        print(f"Tax:          ${order.tax_amount}")
        print(f"Discount:    -${order.discount_amount}")
        print(f"Total:        ${order.total}")
        print(f"Final status: {order.status}")
        print(f"Mailbox:      {mailbox_dir}")
        print(f"Emails captured: {len(mailbox.emails)}")
        for info in mailbox.emails:
            print(f"  - {info['subject']} -> {info['to']}")
    finally:
        await engine.dispose()
        email_tasks._send = original_send
        stripe.PaymentIntent.create = original_stripe_create
        stripe.PaymentIntent.retrieve = original_stripe_retrieve
        celery_app.conf.task_always_eager = original_always_eager


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate a complete client interaction with the e-commerce API."
    )
    parser.add_argument(
        "--mailbox-dir",
        type=Path,
        default=Path(__file__).parent / "mailbox",
        help="Directory where captured emails are saved (default: app/scripts/mailbox).",
    )
    args = parser.parse_args()

    settings = get_settings()
    asyncio.run(simulate(settings, args.mailbox_dir))


if __name__ == "__main__":
    main()
