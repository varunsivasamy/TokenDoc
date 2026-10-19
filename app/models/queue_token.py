import secrets
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import QueueStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.clinic import Clinic
    from app.models.doctor import Doctor
    from app.models.patient import Patient


class QueueToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Queue token entity representing a patient's place in a doctor's live queue."""

    __tablename__ = "queue_tokens"
    __table_args__ = (
        UniqueConstraint(
            "doctor_id", "token_date", "token_number", name="uq_doctor_date_token_num"
        ),
    )

    clinic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    token_number: Mapped[int] = mapped_column(Integer, nullable=False)
    token_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    access_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: f"tk_{secrets.token_urlsafe(8)}",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=QueueStatus.WAITING.value,
        index=True,
    )
    is_emergency: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Lifecycle timestamps
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consultation_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consultation_end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic")
    doctor: Mapped["Doctor"] = relationship("Doctor")
    patient: Mapped["Patient"] = relationship("Patient")
    appointment: Mapped["Appointment | None"] = relationship("Appointment")

    def __repr__(self) -> str:
        return f"<QueueToken doc={self.doctor_id} date={self.token_date} num={self.token_number} status={self.status}>"


class DailyTokenCounter(Base, TimestampMixin):
    """Atomic counter table maintaining deterministic sequence numbers per doctor per day."""

    __tablename__ = "daily_token_counters"
    __table_args__ = (UniqueConstraint("doctor_id", "token_date", name="uq_counter_doctor_date"),)

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"cnt_{secrets.token_hex(8)}",
    )
    clinic_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<DailyTokenCounter doc={self.doctor_id} date={self.token_date} last={self.last_number}>"
