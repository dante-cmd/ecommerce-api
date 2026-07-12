import asyncio
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.product import Category, Product, ProductVariant
from app.models.user import User

settings = get_settings()
engine = create_async_engine(str(settings.database_url))
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed() -> None:
    async with SessionLocal() as session:
        # Admin user
        admin = await session.execute(select(User).where(User.email == settings.seed_admin_email))
        if admin.scalar_one_or_none() is None:
            user = User(
                email=settings.seed_admin_email,
                hashed_password=get_password_hash(settings.seed_admin_password),
                first_name="Admin",
                last_name="User",
                role="admin",
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.flush()
            print(f"Created admin user: {settings.seed_admin_email}")

        # Categories
        electronics = await session.execute(select(Category).where(Category.slug == "electronics"))
        electronics_cat = electronics.scalar_one_or_none()
        if electronics_cat is None:
            cat = Category(name="Electronics", slug="electronics", description="Gadgets and devices")
            session.add(cat)
            await session.flush()
            electronics_id = cat.id
            print("Created category: Electronics")
        else:
            electronics_id = electronics_cat.id

        clothing = await session.execute(select(Category).where(Category.slug == "clothing"))
        clothing_cat = clothing.scalar_one_or_none()
        if clothing_cat is None:
            cat = Category(name="Clothing", slug="clothing", description="Apparel and accessories")
            session.add(cat)
            await session.flush()
            clothing_id = cat.id
            print("Created category: Clothing")
        else:
            clothing_id = clothing_cat.id

        # Products
        existing = await session.execute(select(Product).where(Product.slug == "wireless-headphones"))
        if existing.scalar_one_or_none() is None:
            product = Product(
                name="Wireless Headphones",
                slug="wireless-headphones",
                description="High-quality wireless headphones with noise cancellation.",
                category_id=electronics_id,
                base_price=Decimal("99.99"),
            )
            session.add(product)
            await session.flush()
            session.add(
                ProductVariant(
                    product_id=product.id,
                    sku="WH-001-BLK",
                    color="Black",
                    stock_quantity=50,
                )
            )
            session.add(
                ProductVariant(
                    product_id=product.id,
                    sku="WH-001-WHT",
                    color="White",
                    stock_quantity=30,
                )
            )
            print("Created product: Wireless Headphones")

        existing = await session.execute(select(Product).where(Product.slug == "cotton-t-shirt"))
        if existing.scalar_one_or_none() is None:
            product = Product(
                name="Cotton T-Shirt",
                slug="cotton-t-shirt",
                description="Comfortable 100% cotton t-shirt.",
                category_id=clothing_id,
                base_price=Decimal("19.99"),
            )
            session.add(product)
            await session.flush()
            session.add(
                ProductVariant(
                    product_id=product.id,
                    sku="TS-001-BLK-M",
                    color="Black",
                    size="M",
                    stock_quantity=100,
                )
            )
            session.add(
                ProductVariant(
                    product_id=product.id,
                    sku="TS-001-WHT-L",
                    color="White",
                    size="L",
                    stock_quantity=80,
                )
            )
            print("Created product: Cotton T-Shirt")

        await session.commit()
        print("Seed completed")


if __name__ == "__main__":
    asyncio.run(seed())
