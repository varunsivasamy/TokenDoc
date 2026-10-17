from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.domain.enums import UserRole
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserPublic
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    """Dependency injection factory for AuthService."""
    user_repo = UserRepository(db)
    return AuthService(user_repo)


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Authenticate with email and password to receive a JWT access token."""
    return auth_service.authenticate(credentials)


@router.get("/me", response_model=UserPublic)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPublic:
    """Retrieve details for the currently authenticated user."""
    return UserPublic.model_validate(current_user)


@router.get("/doctor-only")
def doctor_only_endpoint(
    current_user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
) -> dict[str, str]:
    """Test endpoint accessible only to users with the DOCTOR role."""
    return {"message": "Doctor access granted", "doctor": current_user.full_name}
