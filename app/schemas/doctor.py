from pydantic import BaseModel, ConfigDict, Field


class DoctorCreate(BaseModel):
    """Schema for registering a new doctor."""

    full_name: str = Field(..., min_length=2, max_length=255)
    specialty: str = Field(default="General Practice", max_length=100)
    room_number: str = Field(default="Room 1", max_length=50)
    default_slot_duration_minutes: int = Field(default=15, ge=5, le=120)
    user_id: str | None = None


class DoctorUpdate(BaseModel):
    """Schema for updating an existing doctor."""

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    specialty: str | None = Field(default=None, max_length=100)
    room_number: str | None = Field(default=None, max_length=50)
    default_slot_duration_minutes: int | None = Field(default=None, ge=5, le=120)
    is_active: bool | None = None


class DoctorResponse(BaseModel):
    """Schema for doctor profile responses."""

    id: str
    clinic_id: str
    user_id: str | None
    full_name: str
    specialty: str
    room_number: str
    default_slot_duration_minutes: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
