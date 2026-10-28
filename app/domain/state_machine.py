from app.domain.enums import QueueStatus
from app.domain.exceptions import InvalidStateTransitionError

# Single source of truth for queue token lifecycle transitions
LEGAL_TRANSITIONS: dict[QueueStatus, set[QueueStatus]] = {
    QueueStatus.WAITING: {
        QueueStatus.CALLED,
        QueueStatus.CANCELLED,
    },
    QueueStatus.CALLED: {
        QueueStatus.IN_CONSULTATION,
        QueueStatus.NO_SHOW,
        QueueStatus.CANCELLED,
    },
    QueueStatus.IN_CONSULTATION: {
        QueueStatus.COMPLETED,
        QueueStatus.CANCELLED,
    },
    QueueStatus.COMPLETED: set(),  # Terminal state
    QueueStatus.NO_SHOW: set(),  # Terminal state
    QueueStatus.CANCELLED: set(),  # Terminal state
}


def can_transition(current: QueueStatus | str, target: QueueStatus | str) -> bool:
    """Check whether a transition between two queue states is permitted."""
    curr_enum = QueueStatus(current)
    target_enum = QueueStatus(target)
    allowed = LEGAL_TRANSITIONS.get(curr_enum, set())
    return target_enum in allowed


def transition_token(current: QueueStatus | str, target: QueueStatus | str) -> QueueStatus:
    """Validate and transition token state, raising InvalidStateTransitionError if illegal."""
    curr_enum = QueueStatus(current)
    target_enum = QueueStatus(target)

    if not can_transition(curr_enum, target_enum):
        raise InvalidStateTransitionError(
            current_status=curr_enum.value,
            attempted_status=target_enum.value,
        )

    return target_enum
