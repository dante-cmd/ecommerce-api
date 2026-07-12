from decimal import Decimal

import pytest

from app.services.pricing_service import PricingService


def test_calculate_shipping_free():
    assert PricingService.calculate_shipping(Decimal("60.00")) == Decimal("0.00")


def test_calculate_shipping_flat():
    assert PricingService.calculate_shipping(Decimal("30.00")) == Decimal("5.00")


def test_calculate_tax():
    tax = PricingService.calculate_tax(Decimal("100.00"))
    assert tax == Decimal("8.00")


def test_apply_coupon_save10():
    discount, code = PricingService.apply_coupon(Decimal("100.00"), "SAVE10")
    assert discount == Decimal("10.00")
    assert code == "SAVE10"


def test_apply_coupon_invalid():
    discount, code = PricingService.apply_coupon(Decimal("100.00"), "INVALID")
    assert discount == Decimal("0.00")
    assert code is None


def test_calculate_order_totals():
    totals = PricingService.calculate_order_totals(Decimal("100.00"), "SAVE10")
    assert totals["subtotal"] == Decimal("100.00")
    assert totals["discount_amount"] == Decimal("10.00")
    assert totals["shipping_cost"] == Decimal("0.00")  # 90 >= free threshold
    assert totals["tax_amount"] == Decimal("7.20")
    assert totals["total"] == Decimal("97.20")
