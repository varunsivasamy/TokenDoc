from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id, require_role
from app.domain.enums import UserRole
from app.models.clinic import Clinic
from app.models.user import User
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.schedule_repository import ScheduleRepository
from app.schemas.doctor import DoctorCreate, DoctorResponse, DoctorUpdate
from app.schemas.schedule import ScheduleCreate, ScheduleResponse, TimeSlot
from app.services.doctor_service import DoctorService
from app.services.slot_service import SlotService

router = APIRouter(prefix="/doctors", tags=["Doctors"])


def get_doctor_service(
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> DoctorService:
    """Dependency injection factory for DoctorService."""
    repo = DoctorRepository(db, clinic_id)
    return DoctorService(repo)


def get_slot_service(
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> SlotService:
    """Dependency injection factory for SlotService."""
    repo = ScheduleRepository(db, clinic_id)
    return SlotService(repo)


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


@router.post(
    "/{doctor_id}/schedules",
    response_model=ScheduleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Configure doctor weekly working schedule",
)
def set_doctor_schedule(
    doctor_id: str,
    data: ScheduleCreate,
    doctor_service: Annotated[DoctorService, Depends(get_doctor_service)],
    slot_service: Annotated[SlotService, Depends(get_slot_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.SUPER_ADMIN))
    ],
) -> ScheduleResponse:
    """Set working hours and slot length for a specific day of week."""
    # Ensure doctor exists
    doctor_service.get_doctor_by_id(doctor_id)
    schedule = slot_service.set_doctor_schedule(doctor_id, data)
    return ScheduleResponse.model_validate(schedule)


@router.get(
    "/{doctor_id}/slots",
    response_model=list[TimeSlot],
    summary="Generate available appointment slots for date",
)
def get_doctor_slots(
    doctor_id: str,
    slot_date: Annotated[date, Query(alias="date", description="Target date (YYYY-MM-DD)")],
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
    doctor_service: Annotated[DoctorService, Depends(get_doctor_service)],
    slot_service: Annotated[SlotService, Depends(get_slot_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST))
    ],
) -> list[TimeSlot]:
    """Calculate and return available appointment slots in UTC for the requested date."""
    doctor = doctor_service.get_doctor_by_id(doctor_id)
    clinic = db.get(Clinic, clinic_id)
    if not clinic:
        return []

    slots = slot_service.generate_slots_for_date(
        doctor=doctor, clinic=clinic, target_date=slot_date
    )
    return list(slots)
