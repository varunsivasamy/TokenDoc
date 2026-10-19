from datetime import date
from typing import Protocol


class LiveQueueStore(Protocol):
    """Protocol for real-time live queue priority storage (e.g. Redis Sorted Sets or In-Memory)."""

    def add_or_update(
        self, clinic_id: str, doctor_id: str, token_date: date, token_id: str, score: float
    ) -> None:
        """Add or update a token in the doctor's live sorted queue with a priority score."""
        ...

    def remove(self, clinic_id: str, doctor_id: str, token_date: date, token_id: str) -> None:
        """Remove a token from the doctor's live sorted queue."""
        ...

    def get_ordered_token_ids(
        self, clinic_id: str, doctor_id: str, token_date: date
    ) -> list[str]:
        """Return ordered token IDs from lowest score (highest priority) to highest score."""
        ...

    def clear(self, clinic_id: str, doctor_id: str, token_date: date) -> None:
        """Clear the doctor's live queue for the specified date."""
        ...

    def get_score(
        self, clinic_id: str, doctor_id: str, token_date: date, token_id: str
    ) -> float | None:
        """Retrieve the current priority score of a token."""
        ...
