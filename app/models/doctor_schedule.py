from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.clinic import Clinic
    from app.models.doctor import Doctor


class DoctorSchedule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Weekly working schedule for a doctor defining consulting hours and slot duration."""

    __tablename__ = "doctor_schedules"
    __table_args__ = (UniqueConstraint("doctor_id", "day_of_week", name="uq_doctor_day_schedule"),)

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
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic")
    doctor: Mapped["Doctor"] = relationship("Doctor")

    def __repr__(self) -> str:
        return f"<DoctorSchedule doc={self.doctor_id} day={self.day_of_week} {self.start_time}-{self.end_time}>"
