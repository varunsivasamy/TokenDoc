from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.enums import AppointmentStatus
from app.models.appointment import Appointment
from app.repositories.base_repository import BaseTenantRepository


class AppointmentRepository(BaseTenantRepository[Appointment]):
    """Tenant-scoped repository for Appointment entities."""

    def __init__(self, db: Session, clinic_id: str):
        super().__init__(Appointment, db, clinic_id)

    def get_active_by_doctor_and_slot(
        self, doctor_id: str, slot_start: datetime
    ) -> Appointment | None:
        """Find active (BOOKED/CONFIRMED) appointment for doctor at specified slot."""
        statement = self._scoped_query().where(
            Appointment.doctor_id == doctor_id,
            Appointment.slot_start == slot_start,
            Appointment.status.in_([AppointmentStatus.BOOKED, AppointmentStatus.CONFIRMED]),
        )
        return self._db.scalars(statement).first()

    def list_by_doctor_and_date(
        self, doctor_id: str, start_day: datetime, end_day: datetime
    ) -> Sequence[Appointment]:
        """List all appointments for a doctor between range."""
        statement = (
            self._scoped_query()
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.slot_start >= start_day,
                Appointment.slot_start < end_day,
            )
            .order_by(Appointment.slot_start)
        )
        return self._db.scalars(statement).all()
