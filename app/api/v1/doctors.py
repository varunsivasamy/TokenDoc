from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id, require_role
from app.domain.enums import UserRole
from app.models.user import User
from app.repositories.doctor_repository import DoctorRepository
from app.schemas.doctor import DoctorCreate, DoctorResponse, DoctorUpdate
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


def get_doctor_service(
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> DoctorService:
    """Dependency injection factory for DoctorService."""
    repo = DoctorRepository(db, clinic_id)
    return DoctorService(repo)


@router.post(
    "",
    response_model=DoctorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new doctor (Clinic Admin only)",
)
def create_doctor(
    data: DoctorCreate,
    doctor_service: Annotated[DoctorService, Depends(get_doctor_service)],
    _: Annotated[User, Depends(require_role(UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN))],
) -> DoctorResponse:
    """Register a new doctor under the authenticated clinic."""
    doctor = doctor_service.create_doctor(data)
    return DoctorResponse.model_validate(doctor)


@router.get(
    "",
    response_model=list[DoctorResponse],
    summary="List doctors for the clinic",
)
def list_doctors(
    doctor_service: Annotated[DoctorService, Depends(get_doctor_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST))
    ],
    active_only: bool = False,
) -> list[DoctorResponse]:
    """Retrieve list of doctors belonging to the authenticated clinic."""
    doctors = doctor_service.list_doctors(active_only=active_only)
    return [DoctorResponse.model_validate(doc) for doc in doctors]


@router.get(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Get doctor profile by ID",
)
def get_doctor(
    doctor_id: str,
    doctor_service: Annotated[DoctorService, Depends(get_doctor_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST))
    ],
) -> DoctorResponse:
    """Retrieve doctor by ID."""
    doctor = doctor_service.get_doctor_by_id(doctor_id)
    return DoctorResponse.model_validate(doctor)


@router.patch(
    "/{doctor_id}",
    response_model=DoctorResponse,
    summary="Update doctor profile (Clinic Admin only)",
)
def update_doctor(
    doctor_id: str,
    data: DoctorUpdate,
    doctor_service: Annotated[DoctorService, Depends(get_doctor_service)],
    _: Annotated[User, Depends(require_role(UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN))],
) -> DoctorResponse:
    """Update doctor profile details."""
    doctor = doctor_service.update_doctor(doctor_id, data)
    return DoctorResponse.model_validate(doctor)
