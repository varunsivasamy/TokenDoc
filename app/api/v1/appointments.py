from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id, require_role
from app.domain.enums import UserRole
from app.models.user import User
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentResponse,
)
from app.services.booking_service import BookingService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


def get_booking_service(
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
) -> BookingService:
    """Dependency injection factory for BookingService."""
    appointment_repo = AppointmentRepository(db, clinic_id)
    doctor_repo = DoctorRepository(db, clinic_id)
    patient_repo = PatientRepository(db, clinic_id)
    return BookingService(appointment_repo, doctor_repo, patient_repo)


@router.post(
    "",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Book a doctor appointment",
)
def book_appointment(
    data: AppointmentCreate,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
) -> AppointmentResponse:
    """Book appointment, returning 409 Conflict if the slot is already taken."""
    appointment = booking_service.book_appointment(data)
    return AppointmentResponse.model_validate(appointment)


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get appointment details by ID",
)
def get_appointment(
    appointment_id: str,
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
) -> AppointmentResponse:
    """Retrieve appointment details."""
    repo = AppointmentRepository(db, clinic_id)
    appointment = repo.get_by_id(appointment_id)
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )
    return AppointmentResponse.model_validate(appointment)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel an appointment",
)
def cancel_appointment(
    appointment_id: str,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
) -> AppointmentResponse:
    """Cancel appointment and release slot for new bookings."""
    appointment = booking_service.cancel_appointment(appointment_id)
    return AppointmentResponse.model_validate(appointment)


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    summary="Reschedule an appointment to a new slot",
)
def reschedule_appointment(
    appointment_id: str,
    data: AppointmentReschedule,
    booking_service: Annotated[BookingService, Depends(get_booking_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
) -> AppointmentResponse:
    """Reschedule appointment to a new slot, returning 409 if new slot is unavailable."""
    appointment = booking_service.reschedule_appointment(appointment_id, data)
    return AppointmentResponse.model_validate(appointment)
