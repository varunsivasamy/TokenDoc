from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_tenant_id, require_role
from app.domain.enums import UserRole
from app.domain.ports import LiveQueueStore
from app.models.user import User
from app.repositories.doctor_repository import DoctorRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.token_repository import TokenRepository
from app.schemas.queue import (
    QueueItemResponse,
    TokenIssueRequest,
    TokenResponse,
    TokenStatusUpdate,
)
from app.services.live_queue import get_live_queue_store
from app.services.queue_service import QueueService

router = APIRouter(prefix="/queue", tags=["Queue Management"])


def get_queue_service(
    clinic_id: Annotated[str, Depends(get_current_tenant_id)],
    db: Annotated[Session, Depends(get_db)],
    live_queue: Annotated[LiveQueueStore, Depends(get_live_queue_store)],
) -> QueueService:
    """Dependency injection factory for QueueService."""
    token_repo = TokenRepository(db, clinic_id)
    doctor_repo = DoctorRepository(db, clinic_id)
    patient_repo = PatientRepository(db, clinic_id)
    return QueueService(token_repo, doctor_repo, patient_repo, live_queue=live_queue)


@router.post(
    "/tokens",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a walk-in or appointment queue token",
)
def issue_token(
    data: TokenIssueRequest,
    queue_service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.RECEPTIONIST, UserRole.CLINIC_ADMIN, UserRole.DOCTOR))
    ],
) -> TokenResponse:
    """Issue a new sequential queue token with guaranteed atomic gap-free numbering."""
    token = queue_service.issue_token(data)
    return TokenResponse.model_validate(token)


@router.post(
    "/doctors/{doctor_id}/call-next",
    response_model=TokenResponse,
    summary="Call the next patient in doctor's queue",
)
def call_next_patient(
    doctor_id: str,
    queue_service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_role(UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.RECEPTIONIST))],
) -> TokenResponse:
    """Advance queue: emergency patients prioritized first, followed by appointment window, then arrival order."""
    token = queue_service.call_next(doctor_id)
    return TokenResponse.model_validate(token)


@router.patch(
    "/tokens/{token_id}/status",
    response_model=TokenResponse,
    summary="Update token status adhering to state machine rules",
)
def update_token_status(
    token_id: str,
    data: TokenStatusUpdate,
    queue_service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_role(UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.RECEPTIONIST))],
) -> TokenResponse:
    """Transition token state. Returns 422 Unprocessable Entity for invalid transitions."""
    token = queue_service.update_token_status(token_id, data.status)
    return TokenResponse.model_validate(token)


@router.post(
    "/tokens/{token_id}/no-show",
    response_model=TokenResponse,
    summary="Mark a called patient as no-show after waiting timeout",
)
def mark_patient_no_show(
    token_id: str,
    queue_service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[User, Depends(require_role(UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.RECEPTIONIST))],
) -> TokenResponse:
    """Mark a called token as NO_SHOW upon arrival timeout, freeing the queue."""
    token = queue_service.mark_no_show_timeout(token_id)
    return TokenResponse.model_validate(token)


@router.get(
    "/doctors/{doctor_id}",
    response_model=list[QueueItemResponse],
    summary="View active live queue for doctor",
)
def get_doctor_queue(
    doctor_id: str,
    queue_service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[
        User, Depends(require_role(UserRole.DOCTOR, UserRole.CLINIC_ADMIN, UserRole.RECEPTIONIST))
    ],
) -> list[QueueItemResponse]:
    """Retrieve the doctor's live active queue sorted by emergency, appointments, and position."""
    items = queue_service.get_queue_for_doctor(doctor_id)
    return list(items)


@router.post(
    "/doctors/{doctor_id}/rebuild",
    summary="Rebuild live queue from Postgres source of truth",
)
def rebuild_queue_endpoint(
    doctor_id: str,
    queue_service: Annotated[QueueService, Depends(get_queue_service)],
    _: Annotated[
        User,
        Depends(require_role(UserRole.CLINIC_ADMIN, UserRole.DOCTOR, UserRole.RECEPTIONIST)),
    ],
) -> dict[str, int | str]:
    """Startup recovery endpoint to rebuild live queue cache from database."""
    today = datetime.now(UTC).date()
    count = queue_service.rebuild_queue_cache(doctor_id, today)
    return {"status": "rebuilt", "doctor_id": doctor_id, "active_tokens_recovered": count}
