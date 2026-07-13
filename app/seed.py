"""Seed the database with admin user and a large product catalog.

Run automatically by the API container on startup, or manually with:

    python -m app.seed
"""

import asyncio
import random
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


# Categories to create if they don't exist.
CATEGORIES = [
    ("Electronics", "electronics", "Gadgets and electronic devices"),
    ("Clothing", "clothing", "Apparel and accessories"),
    ("Home & Kitchen", "home-kitchen", "Everything for your home"),
    ("Sports", "sports", "Sports gear and outdoor equipment"),
    ("Books", "books", "Physical and digital books"),
    ("Beauty", "beauty", "Beauty and personal care"),
    ("Toys", "toys", "Toys and games for all ages"),
    ("Automotive", "automotive", "Car accessories and tools"),
    ("Garden", "garden", "Gardening and outdoor living"),
    ("Pet Supplies", "pet-supplies", "Supplies for pets"),
]

# Base templates used to build the deterministic 500+ product catalog.
PRODUCT_TEMPLATES = [
    # (category_slug, base_name_template, base_price, variant_type)
    ("electronics", "Wireless Headphones", Decimal("99.99"), "color"),
    ("electronics", "Smart Watch", Decimal("199.99"), "color"),
    ("electronics", "Bluetooth Speaker", Decimal("79.99"), "color"),
    ("electronics", "Laptop Stand", Decimal("49.99"), "color"),
    ("electronics", "USB-C Hub", Decimal("39.99"), "color"),
    ("electronics", "Mechanical Keyboard", Decimal("129.99"), "color"),
    ("electronics", "Wireless Mouse", Decimal("29.99"), "color"),
    ("electronics", "Webcam", Decimal("69.99"), "color"),
    ("electronics", "Monitor Light Bar", Decimal("44.99"), "color"),
    ("electronics", "Portable Charger", Decimal("34.99"), "color"),
    ("electronics", "Noise-Canceling Earbuds", Decimal("149.99"), "color"),
    ("electronics", "Smart Home Hub", Decimal("89.99"), "color"),
    ("clothing", "Cotton T-Shirt", Decimal("19.99"), "size_color"),
    ("clothing", "Denim Jeans", Decimal("59.99"), "size_color"),
    ("clothing", "Running Shoes", Decimal("89.99"), "size_color"),
    ("clothing", "Hooded Sweatshirt", Decimal("49.99"), "size_color"),
    ("clothing", "Polo Shirt", Decimal("34.99"), "size_color"),
    ("clothing", "Cargo Shorts", Decimal("39.99"), "size_color"),
    ("clothing", "Winter Jacket", Decimal("129.99"), "size_color"),
    ("clothing", "Sneakers", Decimal("79.99"), "size_color"),
    ("clothing", "Wool Socks", Decimal("9.99"), "size_color"),
    ("clothing", "Baseball Cap", Decimal("14.99"), "color"),
    ("home-kitchen", "Coffee Maker", Decimal("129.99"), "color"),
    ("home-kitchen", "Non-Stick Cookware Set", Decimal("149.99"), "color"),
    ("home-kitchen", "LED Desk Lamp", Decimal("44.99"), "color"),
    ("home-kitchen", "Air Fryer", Decimal("99.99"), "color"),
    ("home-kitchen", "Blender", Decimal("59.99"), "color"),
    ("home-kitchen", "Toaster", Decimal("39.99"), "color"),
    ("home-kitchen", "Electric Kettle", Decimal("34.99"), "color"),
    ("home-kitchen", "Knife Set", Decimal("79.99"), "color"),
    ("home-kitchen", "Cutting Board", Decimal("19.99"), "color"),
    ("home-kitchen", "Food Storage Containers", Decimal("24.99"), "color"),
    ("sports", "Yoga Mat", Decimal("29.99"), "color"),
    ("sports", "Dumbbell Set", Decimal("249.99"), "color"),
    ("sports", "Tennis Racket", Decimal("119.99"), "color"),
    ("sports", "Basketball", Decimal("24.99"), "color"),
    ("sports", "Soccer Ball", Decimal("22.99"), "color"),
    ("sports", "Jump Rope", Decimal("12.99"), "color"),
    ("sports", "Resistance Bands", Decimal("18.99"), "color"),
    ("sports", "Cycling Helmet", Decimal("59.99"), "color"),
    ("sports", "Hiking Backpack", Decimal("89.99"), "color"),
    ("sports", "Foam Roller", Decimal("21.99"), "color"),
    ("books", "Science Fiction Anthology", Decimal("14.99"), "format"),
    ("books", "Cookbook", Decimal("24.99"), "format"),
    ("books", "Mystery Novel", Decimal("12.99"), "format"),
    ("books", "Biography", Decimal("18.99"), "format"),
    ("books", "Self-Help Guide", Decimal("16.99"), "format"),
    ("books", "Travel Guide", Decimal("19.99"), "format"),
    ("books", "History Book", Decimal("21.99"), "format"),
    ("books", "Children's Picture Book", Decimal("9.99"), "format"),
    ("books", "Art Collection", Decimal("29.99"), "format"),
    ("books", "Programming Manual", Decimal("39.99"), "format"),
    ("beauty", "Moisturizing Cream", Decimal("18.99"), "size"),
    ("beauty", "Shampoo & Conditioner Kit", Decimal("22.99"), "size"),
    ("beauty", "Face Serum", Decimal("28.99"), "size"),
    ("beauty", "Sunscreen Lotion", Decimal("14.99"), "size"),
    ("beauty", "Lip Balm Set", Decimal("8.99"), "color"),
    ("beauty", "Eyeliner Pencil", Decimal("11.99"), "color"),
    ("beauty", "Nail Polish", Decimal("7.99"), "color"),
    ("beauty", "Beard Trimmer", Decimal("34.99"), "color"),
    ("beauty", "Hair Dryer", Decimal("49.99"), "color"),
    ("beauty", "Makeup Brush Set", Decimal("24.99"), "color"),
    ("toys", "Building Blocks Set", Decimal("34.99"), "color"),
    ("toys", "Board Game", Decimal("39.99"), "edition"),
    ("toys", "Puzzle", Decimal("19.99"), "size"),
    ("toys", "Remote Control Car", Decimal("49.99"), "color"),
    ("toys", "Doll House", Decimal("89.99"), "color"),
    ("toys", "Action Figure", Decimal("14.99"), "color"),
    ("toys", "Plush Toy", Decimal("16.99"), "color"),
    ("toys", "Educational Tablet", Decimal("59.99"), "color"),
    ("toys", "Train Set", Decimal("44.99"), "color"),
    ("toys", "Art Supplies Kit", Decimal("24.99"), "color"),
    ("automotive", "Car Phone Mount", Decimal("19.99"), "color"),
    ("automotive", "Seat Covers", Decimal("59.99"), "color"),
    ("automotive", "Floor Mats", Decimal("39.99"), "color"),
    ("automotive", "Dash Cam", Decimal("89.99"), "color"),
    ("automotive", "Tire Pressure Gauge", Decimal("12.99"), "color"),
    ("automotive", "Jump Starter", Decimal("79.99"), "color"),
    ("automotive", "Car Vacuum", Decimal("34.99"), "color"),
    ("automotive", "Steering Wheel Cover", Decimal("14.99"), "color"),
    ("automotive", "LED Headlight Bulbs", Decimal("29.99"), "color"),
    ("automotive", "Cargo Organizer", Decimal("24.99"), "color"),
    ("garden", "Garden Hose", Decimal("29.99"), "color"),
    ("garden", "Planter Pot Set", Decimal("34.99"), "color"),
    ("garden", "Lawn Mower", Decimal("199.99"), "color"),
    ("garden", "Pruning Shears", Decimal("19.99"), "color"),
    ("garden", "Outdoor String Lights", Decimal("24.99"), "color"),
    ("garden", "Compost Bin", Decimal("49.99"), "color"),
    ("garden", "Watering Can", Decimal("14.99"), "color"),
    ("garden", "Bird Feeder", Decimal("18.99"), "color"),
    ("garden", "Patio Umbrella", Decimal("79.99"), "color"),
    ("garden", "Garden Tool Set", Decimal("39.99"), "color"),
    ("pet-supplies", "Dog Bed", Decimal("44.99"), "size"),
    ("pet-supplies", "Cat Tree", Decimal("89.99"), "color"),
    ("pet-supplies", "Pet Food Bowl", Decimal("12.99"), "color"),
    ("pet-supplies", "Leash & Collar Set", Decimal("19.99"), "color"),
    ("pet-supplies", "Pet Carrier", Decimal("59.99"), "color"),
    ("pet-supplies", "Squeaky Toy Pack", Decimal("14.99"), "color"),
    ("pet-supplies", "Scratching Post", Decimal("29.99"), "color"),
    ("pet-supplies", "Automatic Feeder", Decimal("69.99"), "color"),
    ("pet-supplies", "Pet Grooming Kit", Decimal("24.99"), "color"),
    ("pet-supplies", "Training Treats", Decimal("9.99"), "size"),
]

_ADJECTIVES = [
    "Premium", "Classic", "Pro", "Essential", "Ultra", "Compact",
    "Deluxe", "Ergonomic", "Portable", "Durable", "Lightweight",
    "Professional", "Modern", "Vintage", "Eco-Friendly", "Stylish",
    "Heavy-Duty", "Wireless", "Smart", "Digital", "Adjustable",
    "Foldable", "Waterproof", "Insulated", "Breathable", "Soft",
    "Hardcover", "Limited Edition", "Travel", "Daily",
]

_COLORS = ["Black", "White", "Gray", "Blue", "Red", "Green", "Yellow", "Purple", "Pink", "Orange"]
_SIZES = ["S", "M", "L", "XL", "XXL"]
_SHOE_SIZES = ["38", "39", "40", "41", "42", "43", "44", "45"]
_BOOK_FORMATS = ["Hardcover", "Paperback", "E-book Bundle"]
_BEAUTY_SIZES = ["50ml", "100ml", "200ml", "300ml"]
_EDITIONS = ["Standard", "Deluxe", "Collector's"]

_TARGET_PRODUCT_COUNT = 500


def _build_variant_specs(variant_type: str, product_index: int) -> list[dict]:
    """Generate variant specs (sku, color/size, stock) for a product."""
    base_sku = f"PRD-{product_index:05d}"
    stock = random.randint(20, 200)

    if variant_type == "color":
        color_count = random.choice([2, 3, 4])
        return [
            {"sku": f"{base_sku}-{color[:3].upper()}", "color": color, "stock": stock}
            for color in _COLORS[:color_count]
        ]

    if variant_type == "size_color":
        size_count = random.choice([2, 3])
        color_count = random.choice([2, 3])
        specs = []
        for size in _SIZES[:size_count]:
            for color in _COLORS[:color_count]:
                specs.append(
                    {
                        "sku": f"{base_sku}-{size}-{color[:3].upper()}",
                        "size": size,
                        "color": color,
                        "stock": stock,
                    }
                )
        return specs

    if variant_type == "size":
        size_count = random.choice([2, 3, 4])
        return [
            {"sku": f"{base_sku}-{size.replace(' ', '')}", "size": size, "stock": stock}
            for size in _BEAUTY_SIZES[:size_count]
        ]

    if variant_type == "format":
        return [
            {"sku": f"{base_sku}-{fmt[:3].upper()}", "color": fmt, "stock": stock}
            for fmt in _BOOK_FORMATS
        ]

    if variant_type == "edition":
        return [
            {"sku": f"{base_sku}-{edition[:3].upper()}", "color": edition, "stock": stock}
            for edition in _EDITIONS
        ]

    return [{"sku": base_sku, "stock": stock}]


def _generate_catalog(count: int) -> list[dict]:
    """Generate a deterministic catalog of ``count`` products."""
    products = []
    random.seed(42)  # Deterministic across runs
    template_index = 0

    while len(products) < count:
        category, base_name, base_price, variant_type = PRODUCT_TEMPLATES[template_index % len(PRODUCT_TEMPLATES)]
        template_index += 1
        adjective = random.choice(_ADJECTIVES)
        product_name = f"{adjective} {base_name}"
        product_slug = f"{adjective.lower().replace(' ', '-')}-{base_name.lower().replace(' ', '-')}-{len(products) + 1}"
        price_adjustment = Decimal(str(random.uniform(-0.15, 0.25)))
        final_price = max(Decimal("4.99"), (base_price * (Decimal("1") + price_adjustment)).quantize(Decimal("0.01")))

        products.append(
            {
                "name": product_name,
                "slug": product_slug[:255],
                "description": f"{product_name} — high quality and ready for everyday use.",
                "category": category,
                "base_price": final_price,
                "variant_type": variant_type,
                "index": len(products) + 1,
            }
        )

    return products


async def _get_or_create_category(session: AsyncSession, name: str, slug: str, description: str) -> int:
    result = await session.execute(select(Category).where(Category.slug == slug))
    category = result.scalar_one_or_none()
    if category is not None:
        return category.id

    category = Category(name=name, slug=slug, description=description)
    session.add(category)
    await session.flush()
    print(f"Created category: {name}")
    return category.id


async def _create_product(session: AsyncSession, data: dict, category_ids: dict) -> None:
    existing = await session.execute(select(Product).where(Product.slug == data["slug"]))
    if existing.scalar_one_or_none() is not None:
        return

    product = Product(
        name=data["name"],
        slug=data["slug"],
        description=data["description"],
        category_id=category_ids[data["category"]],
        base_price=data["base_price"],
    )
    session.add(product)
    await session.flush()

    for variant_data in _build_variant_specs(data["variant_type"], data["index"]):
        session.add(
            ProductVariant(
                product_id=product.id,
                sku=variant_data["sku"],
                color=variant_data.get("color"),
                size=variant_data.get("size"),
                stock_quantity=variant_data["stock"],
            )
        )


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
        category_ids = {}
        for name, slug, description in CATEGORIES:
            category_ids[slug] = await _get_or_create_category(session, name, slug, description)

        # Products
        catalog = _generate_catalog(_TARGET_PRODUCT_COUNT)
        created = 0
        skipped = 0
        for product_data in catalog:
            existing = await session.execute(select(Product).where(Product.slug == product_data["slug"]))
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue
            await _create_product(session, product_data, category_ids)
            created += 1
            if created % 100 == 0:
                print(f"Created {created} products...")

        await session.commit()
        print(f"Seed completed: {created} products created, {skipped} already existed")


if __name__ == "__main__":
    asyncio.run(seed())
