from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.models.product import Category, Product, ProductImage, ProductVariant, Review
from app.repositories.product_repository import ProductRepository
from app.schemas.product import (
    ProductCreate,
    ProductReviewCreate,
    ProductSearchFilters,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantUpdate,
)


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProductRepository(session)

    async def create_category(self, name: str, slug: str, description: str | None = None) -> Category:
        existing = await self.repo.get_category_by_slug(slug)
        if existing:
            raise ConflictException("Category slug already exists")
        category = Category(name=name, slug=slug, description=description)
        return await self.repo.create(category)

    async def list_categories(self) -> list[Category]:
        return await self.repo.list_categories()

    async def create_product(self, data: ProductCreate) -> Product:
        category = await self.repo.get_category_by_id(data.category_id)
        if not category:
            raise NotFoundException("Category not found")

        existing = await self.repo.get_by_slug(data.slug)
        if existing:
            raise ConflictException("Product slug already exists")

        product = Product(
            name=data.name,
            slug=data.slug,
            description=data.description,
            category_id=data.category_id,
            base_price=data.base_price,
        )
        product.category = category
        await self.repo.create(product)

        for variant_data in data.variants:
            if await self.repo.sku_exists(variant_data.sku):
                raise ConflictException(f"SKU {variant_data.sku} already exists")
            variant = ProductVariant(
                product_id=product.id,
                sku=variant_data.sku,
                size=variant_data.size,
                color=variant_data.color,
                price_adjustment=variant_data.price_adjustment,
                stock_quantity=variant_data.stock_quantity,
            )
            self.session.add(variant)

        for image_data in data.images:
            image = ProductImage(
                product_id=product.id,
                url=image_data.url,
                is_primary=image_data.is_primary,
                order=image_data.order,
            )
            self.session.add(image)

        await self.session.flush()
        await self.session.refresh(product, attribute_names=["variants", "images", "category"])
        return product

    async def update_product(self, product_id: int, data: ProductUpdate) -> Product:
        product = await self.repo.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product not found")

        if data.slug and data.slug != product.slug:
            existing = await self.repo.get_by_slug(data.slug)
            if existing:
                raise ConflictException("Product slug already exists")

        for field in ["name", "slug", "description", "category_id", "base_price", "is_active"]:
            value = getattr(data, field)
            if value is not None:
                setattr(product, field, value)

        return await self.repo.update(product)

    async def update_variant(
        self, variant_id: int, data: ProductVariantUpdate
    ) -> ProductVariant:
        variant = await self.repo.get_variant_by_id(variant_id)
        if not variant:
            raise NotFoundException("Variant not found")

        if data.sku and data.sku != variant.sku:
            if await self.repo.sku_exists(data.sku):
                raise ConflictException("SKU already exists")
            variant.sku = data.sku

        for field in ["size", "color", "price_adjustment", "stock_quantity", "is_active"]:
            value = getattr(data, field)
            if value is not None:
                setattr(variant, field, value)

        self.session.add(variant)
        await self.session.flush()
        await self.session.refresh(variant)
        return variant

    async def add_review(
        self, user_id: int, product_id: int, data: ProductReviewCreate
    ) -> Review:
        product = await self.repo.get_by_id(product_id)
        if not product:
            raise NotFoundException("Product not found")

        is_verified = await self.repo.has_user_purchased_product(user_id, product_id)
        review = Review(
            product_id=product_id,
            user_id=user_id,
            rating=data.rating,
            comment=data.comment,
            is_verified_purchase=is_verified,
        )
        self.session.add(review)
        await self.session.flush()
        await self.repo.update_product_rating(product_id)
        await self.session.refresh(review)
        return review

    async def search_products(self, filters: ProductSearchFilters):
        return await self.repo.search_products(filters)

    async def get_product_by_slug(self, slug: str) -> Product:
        product = await self.repo.get_by_slug(slug)
        if not product:
            raise NotFoundException("Product not found")
        return product

    async def get_reviews(self, product_id: int) -> list[Review]:
        return await self.repo.get_reviews_by_product(product_id)
