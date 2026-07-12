from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import UserRole


class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None


class UserOut(UserBase):
    id: int
    role: UserRole
    is_active: bool
    is_verified: bool
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AddressBase(BaseModel):
    label: str | None = None
    street: str
    city: str
    state: str
    postal_code: str
    country: str
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(AddressBase):
    street: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class AddressOut(AddressBase):
    id: int
    user_id: int

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class EmailVerifyRequest(BaseModel):
    token: str
