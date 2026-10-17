from datetime import UTC

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.domain.enums import AppointmentStatus
from app.models.appointment import Appointment
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule


class BookingService:
    """Service encapsulating appointment booking rules, conflict handling, and cancellations."""

    def __init__(
        self,
        appointment_repo: AppointmentRepository,
        doctor_repo: DoctorRepository,
        patient_repo: PatientRepository,
    ):
        self._repo = appointment_repo
        self._doctor_repo = doctor_repo
        self._patient_repo = patient_repo

    def book_appointment(self, data: AppointmentCreate) -> Appointment:
        """Book an appointment for a patient with a doctor.

        Catches database unique index violations to guarantee strict 409 Conflict responses.
        """
        # Validate doctor exists
        doctor = self._doctor_repo.get_by_id(data.doctor_id)
        if not doctor or not doctor.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found or inactive",
            )

        # Validate patient exists
        patient = self._patient_repo.get_by_id(data.patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found or inactive",
            )

        # Normalize datetimes to UTC
        start_utc = (
            data.slot_start.astimezone(UTC)
            if data.slot_start.tzinfo
            else data.slot_start.replace(tzinfo=UTC)
        )
        end_utc = (
            data.slot_end.astimezone(UTC)
            if data.slot_end.tzinfo
            else data.slot_end.replace(tzinfo=UTC)
        )

        appointment = Appointment(
            doctor_id=data.doctor_id,
            patient_id=data.patient_id,
            slot_start=start_utc,
            slot_end=end_utc,
            status=AppointmentStatus.BOOKED.value,
            notes=data.notes,
        )

        try:
            return self._repo.create(appointment)
        except IntegrityError as exc:
            self._repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This slot has already been booked with the doctor",
            ) from exc

    def cancel_appointment(self, appointment_id: str) -> Appointment:
        """Cancel an appointment, freeing the slot for new bookings."""
        appointment = self._repo.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        if appointment.status == AppointmentStatus.CANCELLED.value:
            return appointment

        appointment.status = AppointmentStatus.CANCELLED.value
        self._repo.db.commit()
        self._repo.db.refresh(appointment)
        return appointment

    def reschedule_appointment(
        self, appointment_id: str, data: AppointmentReschedule
    ) -> Appointment:
        """Reschedule an existing appointment to a new slot."""
        appointment = self._repo.get_by_id(appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found",
            )

        new_start_utc = (
            data.new_slot_start.astimezone(UTC)
            if data.new_slot_start.tzinfo
            else data.new_slot_start.replace(tzinfo=UTC)
        )
        new_end_utc = (
            data.new_slot_end.astimezone(UTC)
            if data.new_slot_end.tzinfo
            else data.new_slot_end.replace(tzinfo=UTC)
        )

        appointment.slot_start = new_start_utc
        appointment.slot_end = new_end_utc
        appointment.status = AppointmentStatus.BOOKED.value

        try:
            self._repo.db.commit()
            self._repo.db.refresh(appointment)
            return appointment
        except IntegrityError as exc:
            self._repo.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The requested new slot is already booked with the doctor",
            ) from exc
