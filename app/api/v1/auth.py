from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse
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
