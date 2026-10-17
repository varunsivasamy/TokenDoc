from collections.abc import Sequence

from fastapi import HTTPException, status

from app.models.patient import Patient
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate, PatientUpdate


class PatientService:
    """Service handling business rules for patient management."""

    def __init__(self, patient_repo: PatientRepository):
        self._repo = patient_repo

    def create_patient(self, data: PatientCreate) -> Patient:
        """Register a new patient, rejecting duplicate phone numbers within the clinic with 409 Conflict."""
        existing = self._repo.get_by_phone(data.phone)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A patient with this phone number is already registered in this clinic",
            )

        patient = Patient(
            full_name=data.full_name,
            phone=data.phone.strip(),
            email=data.email,
            date_of_birth=data.date_of_birth,
            gender=data.gender,
            medical_record_number=data.medical_record_number.strip(),
        )
        return self._repo.create(patient)

    def list_patients(self, offset: int = 0, limit: int = 50) -> Sequence[Patient]:
        """List patients paginated for the current clinic."""
        return self._repo.list_all(offset=offset, limit=limit)

    def search_patients(self, query: str, offset: int = 0, limit: int = 20) -> Sequence[Patient]:
        """Search patients by name, phone, or MRN."""
        return self._repo.search(query=query, offset=offset, limit=limit)

    def get_patient_by_id(self, patient_id: str) -> Patient:
        """Retrieve patient by ID or raise 404."""
        patient = self._repo.get_by_id(patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found",
            )
        return patient

    def update_patient(self, patient_id: str, data: PatientUpdate) -> Patient:
        """Update patient details, preventing duplicate phone conflict."""
        patient = self.get_patient_by_id(patient_id)

        update_dict = data.model_dump(exclude_unset=True)
        if "phone" in update_dict and update_dict["phone"] != patient.phone:
            existing = self._repo.get_by_phone(update_dict["phone"])
            if existing and existing.id != patient.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A patient with this phone number is already registered in this clinic",
                )

        for key, value in update_dict.items():
            setattr(patient, key, value)

        self._repo.db.commit()
        self._repo.db.refresh(patient)
        return patient
