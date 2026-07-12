from decimal import Decimal
from typing import Any

from app.schemas.cart import CartOut


class PricingService:
    TAX_RATE = Decimal("0.08")
    FREE_SHIPPING_THRESHOLD = Decimal("50.00")
    FLAT_SHIPPING_COST = Decimal("5.00")

    @classmethod
    def calculate_shipping(cls, subtotal: Decimal) -> Decimal:
        if subtotal >= cls.FREE_SHIPPING_THRESHOLD:
            return Decimal("0.00")
        return cls.FLAT_SHIPPING_COST

    @classmethod
    def calculate_tax(cls, subtotal: Decimal) -> Decimal:
        return (subtotal * cls.TAX_RATE).quantize(Decimal("0.01"))

    @classmethod
    def apply_coupon(cls, subtotal: Decimal, coupon_code: str | None) -> tuple[Decimal, str | None]:
        # Simplified coupon logic: 10% off with code SAVE10
        if not coupon_code:
            return Decimal("0.00"), None
        normalized = coupon_code.strip().upper()
        if normalized == "SAVE10":
            return (subtotal * Decimal("0.10")).quantize(Decimal("0.01")), normalized
        return Decimal("0.00"), None

    @classmethod
    def calculate_order_totals(
        cls, subtotal: Decimal, coupon_code: str | None
    ) -> dict[str, Decimal]:
        discount_amount, _ = cls.apply_coupon(subtotal, coupon_code)
        shipping_cost = cls.calculate_shipping(subtotal - discount_amount)
        taxable_amount = subtotal - discount_amount
        tax_amount = cls.calculate_tax(taxable_amount)
        total = taxable_amount + shipping_cost + tax_amount
        return {
            "subtotal": subtotal,
            "shipping_cost": shipping_cost,
            "tax_amount": tax_amount,
            "discount_amount": discount_amount,
            "total": total,
        }

    @classmethod
    def calculate_cart_subtotal(cls, cart: CartOut) -> Decimal:
        return sum(item.total_price for item in cart.items)
