from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException, ValidationException
from app.models.cart import Cart, CartItem

from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.cart import CartItemOut, CartItemCreate, CartItemUpdate, CartOut


class CartService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cart_repo = CartRepository(session)
        self.product_repo = ProductRepository(session)

    async def _ensure_user_cart(self, user_id: int | None, session_id: str | None) -> Cart:
        if user_id:
            cart = await self.cart_repo.get_by_user_id(user_id)
            if cart:
                return cart
            cart = Cart(user_id=user_id)
            return await self.cart_repo.create(cart)

        if session_id:
            cart = await self.cart_repo.get_by_session_id(session_id)
            if cart:
                return cart
            cart = Cart(session_id=session_id)
            return await self.cart_repo.create(cart)

        raise ValidationException("Either user_id or session_id is required")

    async def get_or_create_cart(
        self, user_id: int | None = None, session_id: str | None = None
    ) -> Cart:
        return await self._ensure_user_cart(user_id, session_id)

    async def add_item(
        self, data: CartItemCreate, user_id: int | None = None, session_id: str | None = None
    ) -> Cart:
        cart = await self._ensure_user_cart(user_id, session_id)
        variant = await self.product_repo.get_variant_by_id(data.variant_id)
        if not variant or not variant.is_active:
            raise NotFoundException("Variant not found")

        if variant.stock_quantity < data.quantity:
            raise ValidationException("Insufficient stock")

        existing = await self.cart_repo.get_cart_item(cart.id, variant.id)
        if existing:
            new_qty = existing.quantity + data.quantity
            if variant.stock_quantity < new_qty:
                raise ValidationException("Insufficient stock")
            existing.quantity = new_qty
        else:
            item = CartItem(cart_id=cart.id, variant_id=variant.id, quantity=data.quantity)
            self.session.add(item)

        await self.session.flush()
        return await self._refresh_cart(cart.id)

    async def update_item(
        self, item_id: int, data: CartItemUpdate, user_id: int | None, session_id: str | None
    ) -> Cart:
        cart = await self._ensure_user_cart(user_id, session_id)
        item = await self.cart_repo.get_cart_item_by_id(item_id)
        if not item or item.cart_id != cart.id:
            raise NotFoundException("Cart item not found")

        if data.quantity == 0:
            await self.cart_repo.delete(item)
        else:
            if item.variant.stock_quantity < data.quantity:
                raise ValidationException("Insufficient stock")
            item.quantity = data.quantity
            self.session.add(item)

        await self.session.flush()
        return await self._refresh_cart(cart.id)

    async def remove_item(self, item_id: int, user_id: int | None, session_id: str | None) -> Cart:
        cart = await self._ensure_user_cart(user_id, session_id)
        item = await self.cart_repo.get_cart_item_by_id(item_id)
        if not item or item.cart_id != cart.id:
            raise NotFoundException("Cart item not found")
        await self.cart_repo.delete(item)
        return await self._refresh_cart(cart.id)

    async def clear_cart(self, user_id: int | None, session_id: str | None) -> None:
        cart = await self._ensure_user_cart(user_id, session_id)
        for item in cart.items:
            await self.cart_repo.delete(item)

    async def merge_session_cart(self, session_id: str, user_id: int) -> Cart:
        session_cart = await self.cart_repo.get_by_session_id(session_id)
        if not session_cart or not session_cart.items:
            return await self._ensure_user_cart(user_id, None)

        user_cart = await self._ensure_user_cart(user_id, None)
        for item in session_cart.items:
            existing = await self.cart_repo.get_cart_item(user_cart.id, item.variant_id)
            if existing:
                new_qty = existing.quantity + item.quantity
                if item.variant.stock_quantity < new_qty:
                    new_qty = item.variant.stock_quantity
                existing.quantity = new_qty
            else:
                new_item = CartItem(
                    cart_id=user_cart.id, variant_id=item.variant_id, quantity=item.quantity
                )
                self.session.add(new_item)

        await self.session.delete(session_cart)
        await self.session.flush()
        return await self._refresh_cart(user_cart.id)

    async def _refresh_cart(self, cart_id: int) -> Cart:
        cart = await self.cart_repo.get_by_id_with_items(cart_id)
        if not cart:
            raise NotFoundException("Cart not found")
        return cart

    @staticmethod
    def to_cart_out(cart: Cart) -> CartOut:
        items = []
        subtotal = Decimal("0.00")
        for item in cart.items:
            variant = item.variant
            unit_price = Decimal(str(variant.product.base_price)) + Decimal(
                str(variant.price_adjustment or Decimal("0.00"))
            )
            total_price = unit_price * item.quantity
            subtotal += total_price
            items.append(
                CartItemOut(
                    id=item.id,
                    variant=variant,
                    quantity=item.quantity,
                    unit_price=unit_price,
                    total_price=total_price,
                )
            )
        return CartOut(
            id=cart.id,
            items=items,
            subtotal=subtotal,
            item_count=sum(item.quantity for item in cart.items),
        )
