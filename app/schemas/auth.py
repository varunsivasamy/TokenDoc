from pydantic import BaseModel, ConfigDict, EmailStr

from app.domain.enums import UserRole


class LoginRequest(BaseModel):
    """Schema for user login credentials."""

    email: EmailStr | str
    password: str


class UserPublic(BaseModel):
    """Public user representation returned in API responses."""

    id: str
    email: str
    full_name: str
    role: UserRole
    clinic_id: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Schema for successful authentication response with JWT access token."""

    access_token: str
    token_type: str = "bearer"
    user: UserPublic
