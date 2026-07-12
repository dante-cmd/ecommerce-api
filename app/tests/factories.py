import factory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.product import Category, Product, ProductVariant
from app.models.user import User


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session_persistence = "flush"

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    hashed_password = factory.LazyAttribute(lambda _: get_password_hash("Password123!"))
    first_name = "Test"
    last_name = "User"
    role = "customer"
    is_active = True
    is_verified = True


class CategoryFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Category
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class ProductFactory(SQLAlchemyModelFactory):
    class Meta:
        model = Product
        sqlalchemy_session_persistence = "flush"

    name = factory.Sequence(lambda n: f"Product {n}")
    slug = factory.Sequence(lambda n: f"product-{n}")
    description = "A great product"
    base_price = 29.99
    is_active = True
    category = factory.SubFactory(CategoryFactory)


class ProductVariantFactory(SQLAlchemyModelFactory):
    class Meta:
        model = ProductVariant
        sqlalchemy_session_persistence = "flush"

    sku = factory.Sequence(lambda n: f"SKU-{n}")
    stock_quantity = 100
    is_active = True
    product = factory.SubFactory(ProductFactory)
