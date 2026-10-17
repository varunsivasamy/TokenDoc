from collections.abc import Sequence

from fastapi import HTTPException, status

from app.models.doctor import Doctor
from app.repositories.doctor_repository import DoctorRepository
from app.schemas.doctor import DoctorCreate, DoctorUpdate


class DoctorService:
    """Service handling business rules for doctor management."""

    def __init__(self, doctor_repo: DoctorRepository):
        self._repo = doctor_repo

    def create_doctor(self, data: DoctorCreate) -> Doctor:
        """Create a new doctor within the authenticated clinic."""
        doctor = Doctor(
            full_name=data.full_name,
            specialty=data.specialty,
            room_number=data.room_number,
            default_slot_duration_minutes=data.default_slot_duration_minutes,
            user_id=data.user_id,
        )
        return self._repo.create(doctor)

    def list_doctors(self, active_only: bool = False) -> Sequence[Doctor]:
        """List doctors for the authenticated clinic."""
        if active_only:
            return self._repo.list_active()
        return self._repo.list_all()

    def get_doctor_by_id(self, doctor_id: str) -> Doctor:
        """Get a single doctor by ID or raise 404."""
        doctor = self._repo.get_by_id(doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found",
            )
        return doctor

    def update_doctor(self, doctor_id: str, data: DoctorUpdate) -> Doctor:
        """Update doctor attributes or raise 404."""
        doctor = self.get_doctor_by_id(doctor_id)

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(doctor, key, value)

        self._repo.db.commit()
        self._repo.db.refresh(doctor)
        return doctor
