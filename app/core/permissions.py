from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.roles import UserRole
from app.core.security import get_current_user_id, get_optional_current_user_id
from app.models.user import User
from app.repositories.user_repository import UserRepository

async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


async def require_staff_or_admin(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or user.role not in {UserRole.STAFF.value, UserRole.ADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Staff or admin required"
        )
    return user


async def get_optional_current_user(
    user_id: int | None = Depends(get_optional_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if user_id is None:
        return None
    return await UserRepository(db).get_by_id(user_id)
