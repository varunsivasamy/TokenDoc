from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Repository handling database operations for User entities."""

    def __init__(self, db: Session):
        self._db = db

    def get_by_id(self, user_id: str) -> User | None:
        """Find user by unique primary key ID."""
        statement = select(User).where(User.id == user_id)
        return self._db.scalars(statement).first()

    def get_by_email(self, email: str) -> User | None:
        """Find user by email address."""
        statement = select(User).where(User.email == email.lower().strip())
        return self._db.scalars(statement).first()

    def create(self, user: User) -> User:
        """Persist a new User entity."""
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user
