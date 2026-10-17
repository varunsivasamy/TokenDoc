from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PatientCreate(BaseModel):
    """Schema for registering a new patient."""

    full_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=5, max_length=50)
    email: EmailStr | str | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    medical_record_number: str = Field(..., min_length=1, max_length=50)


class PatientUpdate(BaseModel):
    """Schema for updating patient details."""

    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    phone: str | None = Field(default=None, min_length=5, max_length=50)
    email: EmailStr | str | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=20)
    medical_record_number: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class PatientResponse(BaseModel):
    """Schema for patient responses."""

    id: str
    clinic_id: str
    full_name: str
    phone: str
    email: str | None
    date_of_birth: date | None
    gender: str | None
    medical_record_number: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
