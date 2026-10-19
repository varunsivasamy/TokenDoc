from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.doctor_schedule import DoctorSchedule
from app.repositories.base_repository import BaseTenantRepository


class ScheduleRepository(BaseTenantRepository[DoctorSchedule]):
    """Tenant-scoped repository for DoctorSchedule entities."""

    def __init__(self, db: Session, clinic_id: str):
        super().__init__(DoctorSchedule, db, clinic_id)

    def get_by_doctor_and_day(self, doctor_id: str, day_of_week: int) -> DoctorSchedule | None:
        """Find active schedule for doctor on a specific day of the week (0=Mon, 6=Sun)."""
        statement = self._scoped_query().where(
            DoctorSchedule.doctor_id == doctor_id,
            DoctorSchedule.day_of_week == day_of_week,
            DoctorSchedule.is_active.is_(True),
        )
        return self._db.scalars(statement).first()

    def list_by_doctor(self, doctor_id: str) -> Sequence[DoctorSchedule]:
        """List all schedule records for a doctor."""
        statement = (
            self._scoped_query()
            .where(DoctorSchedule.doctor_id == doctor_id)
            .order_by(DoctorSchedule.day_of_week)
        )
        return self._db.scalars(statement).all()
