from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.v1.deps import DbDep
from app.core.permissions import get_current_user, require_admin
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.user import AddressCreate, AddressOut, AddressUpdate, UserOut, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(data: UserUpdate, db: DbDep, current_user: User = Depends(get_current_user)):
    service = UserService(db)
    return await service.update_profile(current_user.id, data)


@router.get("/me/addresses", response_model=list[AddressOut])
async def list_addresses(db: DbDep, current_user: User = Depends(get_current_user)):
    service = UserService(db)
    return await service.list_addresses(current_user.id)


@router.post("/me/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(data: AddressCreate, db: DbDep, current_user: User = Depends(get_current_user)):
    service = UserService(db)
    return await service.create_address(current_user.id, data)


@router.patch("/me/addresses/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: int, data: AddressUpdate, db: DbDep, current_user: User = Depends(get_current_user)
):
    service = UserService(db)
    return await service.update_address(current_user.id, address_id, data)


@router.delete("/me/addresses/{address_id}", response_model=MessageResponse)
async def delete_address(address_id: int, db: DbDep, current_user: User = Depends(get_current_user)):
    service = UserService(db)
    await service.delete_address(current_user.id, address_id)
    return MessageResponse(message="Address deleted")
