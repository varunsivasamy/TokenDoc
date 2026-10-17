from enum import StrEnum


class UserRole(StrEnum):
    """User roles for authentication and role-based access control (RBAC)."""

    SUPER_ADMIN = "SUPER_ADMIN"
    CLINIC_ADMIN = "CLINIC_ADMIN"
    DOCTOR = "DOCTOR"
    RECEPTIONIST = "RECEPTIONIST"


class QueueStatus(StrEnum):
    """Lifecycle states for queue tokens."""

    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_CONSULTATION = "IN_CONSULTATION"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"


class AppointmentStatus(StrEnum):
    """Status options for scheduled doctor appointments."""

    BOOKED = "BOOKED"
    CONFIRMED = "CONFIRMED"
    IN_CONSULTATION = "IN_CONSULTATION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"
