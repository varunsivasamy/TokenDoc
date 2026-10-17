from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.domain.enums import UserRole
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User account entity belonging to a clinic tenant (or super admin)."""

    __tablename__ = "users"

    clinic_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(String(50), nullable=False, default=UserRole.RECEPTIONIST)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    clinic: Mapped["Clinic | None"] = relationship("Clinic", back_populates="users")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"
