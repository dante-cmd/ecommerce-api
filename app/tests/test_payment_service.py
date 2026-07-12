from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.order import Order
from app.models.user import User
from app.services.payment_service import PaymentService


@pytest.fixture
def payment_service(db_session: AsyncSession, settings: Settings):
    return PaymentService(db_session, settings)


@pytest.mark.asyncio
async def test_create_payment_intent(payment_service: PaymentService, db_session: AsyncSession):
    user = User(email="pay@example.com", hashed_password="x", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()
    order = Order(
        user_id=user.id,
        status="pending",
        shipping_address="123",
        subtotal=Decimal("50.00"),
        shipping_cost=Decimal("5.00"),
        tax_amount=Decimal("4.40"),
        discount_amount=Decimal("0.00"),
        total=Decimal("59.40"),
    )
    db_session.add(order)
    await db_session.flush()

    mock_intent = MagicMock()
    mock_intent.id = "pi_test"
    mock_intent.client_secret = "pi_test_secret"

    with patch("stripe.PaymentIntent.create", return_value=mock_intent):
        result = await payment_service.create_payment_intent(order.id, user.id)
        assert result.payment_intent_id == "pi_test"
        assert result.client_secret == "pi_test_secret"
