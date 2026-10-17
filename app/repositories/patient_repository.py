from collections.abc import Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.repositories.base_repository import BaseTenantRepository


class PatientRepository(BaseTenantRepository[Patient]):
    """Tenant-scoped repository for Patient entities."""

    def __init__(self, db: Session, clinic_id: str):
        super().__init__(Patient, db, clinic_id)

    def get_by_phone(self, phone: str) -> Patient | None:
        """Find patient with phone number in the current clinic."""
        clean_phone = phone.strip()
        statement = self._scoped_query().where(Patient.phone == clean_phone)
        return self._db.scalars(statement).first()

    def get_by_mrn(self, mrn: str) -> Patient | None:
        """Find patient by medical record number in the current clinic."""
        clean_mrn = mrn.strip()
        statement = self._scoped_query().where(Patient.medical_record_number == clean_mrn)
        return self._db.scalars(statement).first()

    def search(self, query: str, offset: int = 0, limit: int = 20) -> Sequence[Patient]:
        """Search patients by name or phone prefix/substring within the current clinic."""
        pattern = f"%{query.strip()}%"
        statement = (
            self._scoped_query()
            .where(
                or_(
                    Patient.full_name.ilike(pattern),
                    Patient.phone.like(pattern),
                    Patient.medical_record_number.ilike(pattern),
                )
            )
            .offset(offset)
            .limit(limit)
        )
        return self._db.scalars(statement).all()
