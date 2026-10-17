from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AppointmentStatus
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.doctor import Doctor
    from app.models.patient import Patient


class Appointment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Appointment entity with partial unique index to guarantee zero double-booking."""

    __tablename__ = "appointments"
    __table_args__ = (
        Index(
            "uq_active_doctor_slot",
            "doctor_id",
            "slot_start",
            unique=True,
            postgresql_where=text("status IN ('BOOKED', 'CONFIRMED')"),
            sqlite_where=text("status IN ('BOOKED', 'CONFIRMED')"),
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
    slot_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=AppointmentStatus.BOOKED.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic")
    doctor: Mapped["Doctor"] = relationship("Doctor")
    patient: Mapped["Patient"] = relationship("Patient")

    def __repr__(self) -> str:
        return f"<Appointment id={self.id} doc={self.doctor_id} start={self.slot_start} status={self.status}>"
