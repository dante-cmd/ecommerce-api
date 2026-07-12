import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.models.product import Category, Product, ProductVariant
from app.models.user import User
from app.schemas.product import ProductCreate, ProductReviewCreate, ProductVariantCreate
from app.services.product_service import ProductService


@pytest.fixture
def product_service(db_session: AsyncSession):
    return ProductService(db_session)


@pytest.mark.asyncio
async def test_create_category(product_service: ProductService, db_session: AsyncSession):
    category = await product_service.create_category("Books", "books", "Readings")
    assert category.name == "Books"
    assert category.slug == "books"


@pytest.mark.asyncio
async def test_create_product(product_service: ProductService, db_session: AsyncSession):
    category = Category(name="Electronics", slug="electronics")
    db_session.add(category)
    await db_session.flush()

    data = ProductCreate(
        name="Smartphone",
        slug="smartphone",
        category_id=category.id,
        base_price=499.99,
        variants=[ProductVariantCreate(sku="SP-001", stock_quantity=10)],
    )
    product = await product_service.create_product(data)
    assert product.name == "Smartphone"
    assert len(product.variants) == 1


@pytest.mark.asyncio
async def test_create_product_duplicate_slug(product_service: ProductService, db_session: AsyncSession):
    category = Category(name="Home", slug="home")
    db_session.add(category)
    await db_session.flush()

    data = ProductCreate(name="Lamp", slug="lamp", category_id=category.id, base_price=29.99)
    await product_service.create_product(data)
    with pytest.raises(ConflictException):
        await product_service.create_product(data)


@pytest.mark.asyncio
async def test_add_review_verified_purchase(product_service: ProductService, db_session: AsyncSession):
    user = User(email="reviewer@example.com", hashed_password="x", is_active=True, is_verified=True)
    category = Category(name="Toys", slug="toys")
    db_session.add_all([user, category])
    await db_session.flush()

    product = Product(name="Toy", slug="toy", category_id=category.id, base_price=10.00)
    db_session.add(product)
    await db_session.flush()

    review = await product_service.add_review(user.id, product.id, ProductReviewCreate(rating=5, comment="Great"))
    assert review.rating == 5
    assert review.is_verified_purchase is False
