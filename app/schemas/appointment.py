from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AppointmentStatus


class AppointmentCreate(BaseModel):
    """Schema for booking a new appointment."""

    doctor_id: str
    patient_id: str
    slot_start: datetime
    slot_end: datetime
    notes: str | None = Field(default=None, max_length=1000)


class AppointmentResponse(BaseModel):
    """Schema for appointment responses."""

    id: str
    clinic_id: str
    doctor_id: str
    patient_id: str
    slot_start: datetime
    slot_end: datetime
    status: AppointmentStatus
    notes: str | None

    model_config = ConfigDict(from_attributes=True)


class AppointmentReschedule(BaseModel):
    """Schema for rescheduling an existing appointment to a new slot."""

    new_slot_start: datetime
    new_slot_end: datetime
