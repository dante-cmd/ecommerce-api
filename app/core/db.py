from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column

from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(str(settings.database_url), echo=settings.debug, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class TimestampMixin:
    """created_at / updated_at stamps in UTC for any table that wants them.

    Note: use a lambda, not datetime.now(timezone.utc) directly, so the
    default is evaluated per-row at insert time, not once at import time.
    The onupdate on updated_at fires on every ORM UPDATE; raw SQL updates
    bypass it (a DB trigger would be needed for full coverage).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
