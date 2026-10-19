from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class ScheduleCreate(BaseModel):
    """Schema for configuring a doctor's weekly work hours on a specific day."""

    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time
    slot_duration_minutes: int = Field(default=15, ge=5, le=120)


class ScheduleResponse(BaseModel):
    """Schema for doctor schedule responses."""

    id: str
    clinic_id: str
    doctor_id: str
    day_of_week: int
    start_time: time
    end_time: time
    slot_duration_minutes: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TimeSlot(BaseModel):
    """Schema representing an individual bookable appointment slot in UTC."""

    slot_start: datetime
    slot_end: datetime
    is_available: bool = True
