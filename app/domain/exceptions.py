class ClinicQDomainException(Exception):
    """Base exception for all domain-level business rule violations."""

    pass


class InvalidStateTransitionError(ClinicQDomainException):
    """Raised when an illegal queue state machine transition is attempted."""

    def __init__(self, current_status: str, attempted_status: str):
        self.current_status = current_status
        self.attempted_status = attempted_status
        super().__init__(
            f"Illegal state transition from '{current_status}' to '{attempted_status}'"
        )
