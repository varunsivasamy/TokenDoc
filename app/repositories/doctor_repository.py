from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.repositories.base_repository import BaseTenantRepository


class DoctorRepository(BaseTenantRepository[Doctor]):
    """Tenant-scoped repository for Doctor entities."""

    def __init__(self, db: Session, clinic_id: str):
        super().__init__(Doctor, db, clinic_id)

    def list_active(self) -> Sequence[Doctor]:
        """List all active doctors in the current clinic."""
        statement = self._scoped_query().where(Doctor.is_active.is_(True))
        return self._db.scalars(statement).all()

    def get_by_user_id(self, user_id: str) -> Doctor | None:
        """Find doctor associated with a specific user account within this clinic."""
        statement = self._scoped_query().where(Doctor.user_id == user_id)
        return self._db.scalars(statement).first()
