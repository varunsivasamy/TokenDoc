from collections.abc import Sequence
from datetime import UTC, date, datetime

from fastapi import HTTPException, status

from app.domain.enums import QueueStatus
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.state_machine import transition_token
from app.models.queue_token import QueueToken
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.token_repository import TokenRepository
from app.schemas.queue import QueueItemResponse, TokenIssueRequest


class QueueService:
    """Service managing walk-in token issuance, queue ordering, and state machine lifecycle."""

    def __init__(
        self,
        token_repo: TokenRepository,
        doctor_repo: DoctorRepository,
        patient_repo: PatientRepository,
    ):
        self._repo = token_repo
        self._doctor_repo = doctor_repo
        self._patient_repo = patient_repo

    def issue_token(self, data: TokenIssueRequest, today: date | None = None) -> QueueToken:
        """Issue a new walk-in or appointment token with atomic, gap-free numbering."""
        token_date = today or datetime.now(UTC).date()

        # Validate doctor
        doctor = self._doctor_repo.get_by_id(data.doctor_id)
        if not doctor or not doctor.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found or inactive",
            )

        # Validate patient
        patient = self._patient_repo.get_by_id(data.patient_id)
        if not patient or not patient.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient not found or inactive",
            )

        # Atomic gap-free sequence counter
        next_num = self._repo.get_next_token_number_atomic(doctor.id, token_date)

        token = QueueToken(
            doctor_id=data.doctor_id,
            patient_id=data.patient_id,
            token_number=next_num,
            token_date=token_date,
            is_emergency=data.is_emergency,
            appointment_id=data.appointment_id,
            status=QueueStatus.WAITING.value,
        )
        return self._repo.create(token)

    def update_token_status(self, token_id: str, new_status: QueueStatus | str) -> QueueToken:
        """Apply state machine transition to a token, updating lifecycle timestamps."""
        token = self._repo.get_by_id(token_id)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue token not found",
            )

        try:
            valid_new_status = transition_token(token.status, new_status)
        except InvalidStateTransitionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        now = datetime.now(UTC)
        token.status = valid_new_status.value

        if valid_new_status == QueueStatus.CALLED:
            token.called_at = now
        elif valid_new_status == QueueStatus.IN_CONSULTATION:
            token.consultation_start_at = now
        elif valid_new_status == QueueStatus.COMPLETED:
            token.consultation_end_at = now

        self._repo.db.commit()
        self._repo.db.refresh(token)
        return token

    def call_next(self, doctor_id: str, today: date | None = None) -> QueueToken:
        """Call next patient in queue: Emergency first, then arrival order."""
        token_date = today or datetime.now(UTC).date()
        tokens = self._repo.list_active_tokens_for_doctor(doctor_id, token_date)

        waiting_tokens = [t for t in tokens if t.status == QueueStatus.WAITING.value]
        if not waiting_tokens:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No patients currently waiting in queue",
            )

        # Priority sort: emergency first, then by token number
        waiting_tokens.sort(key=lambda t: (not t.is_emergency, t.token_number))
        next_token = waiting_tokens[0]

        return self.update_token_status(next_token.id, QueueStatus.CALLED)

    def get_queue_for_doctor(
        self, doctor_id: str, today: date | None = None
    ) -> Sequence[QueueItemResponse]:
        """Retrieve active queue ordered by priority and arrival."""
        token_date = today or datetime.now(UTC).date()
        tokens = self._repo.list_active_tokens_for_doctor(doctor_id, token_date)

        active = [
            t
            for t in tokens
            if t.status
            in (
                QueueStatus.WAITING.value,
                QueueStatus.CALLED.value,
                QueueStatus.IN_CONSULTATION.value,
            )
        ]

        # Priority sort:
        # 1. IN_CONSULTATION first
        # 2. CALLED second
        # 3. WAITING: Emergency first, then token_number
        def sort_key(t: QueueToken):
            if t.status == QueueStatus.IN_CONSULTATION.value:
                return (0, 0, t.token_number)
            if t.status == QueueStatus.CALLED.value:
                return (1, 0, t.token_number)
            return (2, 0 if t.is_emergency else 1, t.token_number)

        active.sort(key=sort_key)

        items: list[QueueItemResponse] = []
        for idx, t in enumerate(active, start=1):
            patient = self._patient_repo.get_by_id(t.patient_id)
            items.append(
                QueueItemResponse(
                    token_id=t.id,
                    token_number=t.token_number,
                    patient_name=patient.full_name if patient else "Unknown",
                    status=t.status,
                    is_emergency=t.is_emergency,
                    position=idx,
                )
            )
        return items
