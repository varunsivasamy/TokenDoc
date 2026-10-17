from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.user import User


class Doctor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Doctor profile entity belonging to a clinic tenant."""

    __tablename__ = "doctors"

    clinic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False, default="General Practice")
    room_number: Mapped[str] = mapped_column(String(50), nullable=False, default="Room 1")
    default_slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic")
    user: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<Doctor id={self.id} name={self.full_name} specialty={self.specialty}>"
