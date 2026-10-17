from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id, require_role
from app.domain.enums import UserRole
from app.models.user import User
from app.repositories.patient_repository import PatientRepository
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["Patients"])


def get_patient_service(
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> PatientService:
    """Dependency injection factory for PatientService."""
    repo = PatientRepository(db, clinic_id)
    return PatientService(repo)


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient (Receptionist / Clinic Admin)",
)
def create_patient(
    data: PatientCreate,
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    _: Annotated[
        User,
        Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN)),
    ],
) -> PatientResponse:
    """Register patient with unique phone validation within current clinic."""
    patient = patient_service.create_patient(data)
    return PatientResponse.model_validate(patient)


@router.get(
    "/search",
    response_model=list[PatientResponse],
    summary="Search patients by name or phone with pagination",
)
def search_patients(
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
    q: Annotated[str, Query(min_length=1, description="Search term: name, phone, or MRN")],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[PatientResponse]:
    """Search patients by name, phone, or MRN substring."""
    patients = patient_service.search_patients(query=q, offset=offset, limit=limit)
    return [PatientResponse.model_validate(p) for p in patients]


@router.get(
    "",
    response_model=list[PatientResponse],
    summary="List patients with pagination",
)
def list_patients(
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[PatientResponse]:
    """List patients belonging to the current clinic with pagination."""
    patients = patient_service.list_patients(offset=offset, limit=limit)
    return [PatientResponse.model_validate(p) for p in patients]


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient by ID",
)
def get_patient(
    patient_id: str,
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
) -> PatientResponse:
    """Retrieve patient details by ID."""
    patient = patient_service.get_patient_by_id(patient_id)
    return PatientResponse.model_validate(patient)


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Update patient details",
)
def update_patient(
    patient_id: str,
    data: PatientUpdate,
    patient_service: Annotated[PatientService, Depends(get_patient_service)],
    _: Annotated[
        User,
        Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.SUPER_ADMIN)),
    ],
) -> PatientResponse:
    """Update patient details."""
    patient = patient_service.update_patient(patient_id, data)
    return PatientResponse.model_validate(patient)
