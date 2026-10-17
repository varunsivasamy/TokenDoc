from fastapi import HTTPException, status

from app.core.security import create_access_token, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, TokenResponse, UserPublic


class AuthService:
    """Service encapsulating authentication and credential verification rules."""

    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    def authenticate(self, credentials: LoginRequest) -> TokenResponse:
        """Authenticate user credentials and generate a signed JWT."""
        user = self._user_repo.get_by_email(credentials.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = {
            "sub": user.id,
            "clinic_id": user.clinic_id,
            "role": user.role,
        }
        token = create_access_token(payload)

        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserPublic.model_validate(user),
        )
