from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import QueueStatus


class TokenIssueRequest(BaseModel):
    """Schema for requesting a new walk-in queue token."""

    doctor_id: str
    patient_id: str
    is_emergency: bool = False
    appointment_id: str | None = None


class TokenResponse(BaseModel):
    """Schema for queue token response."""

    id: str
    clinic_id: str
    doctor_id: str
    patient_id: str
    token_number: int
    token_date: date
    access_code: str
    status: QueueStatus | str
    is_emergency: bool
    appointment_id: str | None = None
    called_at: datetime | None = None
    consultation_start_at: datetime | None = None
    consultation_end_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TokenStatusUpdate(BaseModel):
    """Schema for transitioning token lifecycle status."""

    status: QueueStatus


class QueueItemResponse(BaseModel):
    """Live queue item showing queue position and status."""

    token_id: str
    token_number: int
    patient_name: str
    status: str
    is_emergency: bool
    position: int
