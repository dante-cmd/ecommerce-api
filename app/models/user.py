from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin


class User(Base, TimestampMixin):
    """User account model — represents both customers and admins.

    The `role` column distinguishes account types (e.g. "customer", "admin").
    New accounts start inactive and unverified until email verification completes.
    """

    __tablename__ = "users"

    # Primary key; indexed for fast lookups.
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Login identifier. Unique constraint prevents duplicate accounts;
    # indexed since nearly every auth query filters by email.
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # Never store plaintext passwords — only the hash (e.g. bcrypt/argon2).
    hashed_password: Mapped[str] = mapped_column(String(255))

    # Optional profile fields, filled in after registration.
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Text instead of String(n) — CDN/S3 URLs can get very long.
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Authorization role, e.g. "customer" or "admin".
    # Defaults to "customer" — the least privileged role.
    role: Mapped[str] = mapped_column(String(20), default="customer")

    # Soft-disable flag: admins can deactivate without deleting the row
    # (preserves order history, reviews, referential integrity, etc.).
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # Email verification flag. Gated separately from is_active so an
    # account can be verified but later deactivated (or vice versa).
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    # if you delete a user, you want to delete their addresses as well, hence the cascade="all, delete-orphan"
    # lazy="selectin" eagerly loads addresses with a second SELECT ... WHERE IN query —
    # avoids N+1 queries without the row multiplication of a JOIN.
    addresses: Mapped[list["Address"]] = relationship(
        "Address", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    # No cascade here: reviews and orders are kept when a user is deactivated/deleted
    # (historical data for analytics and accounting).
    reviews: Mapped[list["Review"]] = relationship("Review", back_populates="user")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="user")

    # One-to-One relationship with Cart, a user can have only one cart, hence uselist=False
    cart: Mapped["Cart"] = relationship("Cart", back_populates="user", uselist=False)


class Address(Base, TimestampMixin):
    """A saved shipping/billing address belonging to a User.

    A user can store multiple addresses (e.g. "Home", "Work"); the optional
    `label` lets them name each one. Exactly one may be flagged is_default.
    """

    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # ondelete="CASCADE" makes the DATABASE delete address rows when the parent
    # user is deleted — works even if the ORM session isn't involved (raw SQL,
    # migrations, admin tooling). Pairs with the ORM cascade on User.addresses.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Optional nickname for the address ("Home", "Office", ...).
    label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Required address components.
    street: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(100))

    # Marks the user's preferred address for checkout pre-fill.
    # Note: uniqueness of "one default per user" must be enforced in
    # application logic (or a partial unique index), not here.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Back-reference to the owning user (many-to-one side).
    user: Mapped["User"] = relationship("User", back_populates="addresses")