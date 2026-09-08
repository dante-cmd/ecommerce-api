from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from itsdangerous import URLSafeSerializer

from app.api.v1.deps import DbDep, SettingsDep
from app.core.permissions import get_optional_current_user
from app.models.user import User
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartOut
from app.services.cart_service import CartService

router = APIRouter()


def _get_or_create_session_id(request: Request, response: Response, settings: SettingsDep) -> str:
    session_id = request.cookies.get("cart_session_id")
    if not session_id:
        serializer = URLSafeSerializer(settings.secret_key, salt="cart-session")
        host = request.client.host if request.client else "unknown"
        session_id = serializer.dumps({"sid": str(host)})
        response.set_cookie(
            key="cart_session_id",
            value=session_id,
            httponly=True,
            secure=settings.is_production,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
        )
    return session_id

@router.get("", response_model=CartOut)
async def get_cart(
    db: DbDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    current_user: User | None = Depends(get_optional_current_user),
):
    service = CartService(db)
    if current_user:
        cart = await service.get_or_create_cart(user_id=current_user.id)
    else:
        session_id = _get_or_create_session_id(request, response, settings)
        cart = await service.get_or_create_cart(session_id=session_id)
    return service.to_cart_out(cart)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
async def add_cart_item(
    data: CartItemCreate,
    db: DbDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    current_user: User | None = Depends(get_optional_current_user),
):
    service = CartService(db)
    if current_user:
        cart = await service.add_item(data, user_id=current_user.id)
    else:
        session_id = _get_or_create_session_id(request, response, settings)
        cart = await service.add_item(data, session_id=session_id)
    return service.to_cart_out(cart)


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_cart_item(
    item_id: int,
    data: CartItemUpdate,
    db: DbDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    current_user: User | None = Depends(get_optional_current_user),
):
    service = CartService(db)
    if current_user:
        cart = await service.update_item(item_id, data, user_id=current_user.id)
    else:
        session_id = _get_or_create_session_id(request, response, settings)
        cart = await service.update_item(item_id, data, session_id=session_id)
    return service.to_cart_out(cart)


@router.delete("/items/{item_id}", response_model=CartOut)
async def remove_cart_item(
    item_id: int,
    db: DbDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    current_user: User | None = Depends(get_optional_current_user),
):
    service = CartService(db)
    if current_user:
        cart = await service.remove_item(item_id, user_id=current_user.id)
    else:
        session_id = _get_or_create_session_id(request, response, settings)
        cart = await service.remove_item(item_id, session_id=session_id)
    return service.to_cart_out(cart)


@router.post("/merge", response_model=CartOut)
async def merge_cart(
    db: DbDep,
    request: Request,
    response: Response,
    settings: SettingsDep,
    current_user: User | None = Depends(get_optional_current_user),
):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    session_id = request.cookies.get("cart_session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session cart not found")
    service = CartService(db)
    cart = await service.merge_session_cart(session_id, current_user.id)
    response.delete_cookie("cart_session_id")
    return service.to_cart_out(cart)
