import pytest

from app.domain.enums import QueueStatus
from app.domain.exceptions import InvalidStateTransitionError
from app.domain.state_machine import LEGAL_TRANSITIONS, can_transition, transition_token


def test_legal_transitions():
    """Verify all defined legal transitions succeed and return new status."""
    assert transition_token(QueueStatus.WAITING, QueueStatus.CALLED) == QueueStatus.CALLED
    assert transition_token(QueueStatus.WAITING, QueueStatus.CANCELLED) == QueueStatus.CANCELLED

    assert transition_token(QueueStatus.CALLED, QueueStatus.IN_CONSULTATION) == QueueStatus.IN_CONSULTATION
    assert transition_token(QueueStatus.CALLED, QueueStatus.NO_SHOW) == QueueStatus.NO_SHOW
    assert transition_token(QueueStatus.CALLED, QueueStatus.CANCELLED) == QueueStatus.CANCELLED

    assert transition_token(QueueStatus.IN_CONSULTATION, QueueStatus.COMPLETED) == QueueStatus.COMPLETED
    assert transition_token(QueueStatus.IN_CONSULTATION, QueueStatus.CANCELLED) == QueueStatus.CANCELLED


def test_illegal_skip_transitions_raise():
    """Verify illegal jumps across states raise InvalidStateTransitionError."""
    # Cannot jump directly from WAITING to IN_CONSULTATION or COMPLETED
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        transition_token(QueueStatus.WAITING, QueueStatus.IN_CONSULTATION)
    assert "Illegal state transition from 'WAITING' to 'IN_CONSULTATION'" in str(exc_info.value)

    with pytest.raises(InvalidStateTransitionError):
        transition_token(QueueStatus.WAITING, QueueStatus.COMPLETED)

    # Cannot jump directly from CALLED to COMPLETED
    with pytest.raises(InvalidStateTransitionError):
        transition_token(QueueStatus.CALLED, QueueStatus.COMPLETED)


def test_terminal_states_cannot_transition():
    """Verify COMPLETED, NO_SHOW, and CANCELLED cannot transition anywhere."""
    terminal_states = [QueueStatus.COMPLETED, QueueStatus.NO_SHOW, QueueStatus.CANCELLED]

    for terminal in terminal_states:
        assert LEGAL_TRANSITIONS[terminal] == set()
        for target in QueueStatus:
            assert can_transition(terminal, target) is False
            with pytest.raises(InvalidStateTransitionError):
                transition_token(terminal, target)


def test_exhaustive_transition_matrix():
    """Test all possible pairs of QueueStatus against the authoritative transition dictionary."""
    for current in QueueStatus:
        allowed_targets = LEGAL_TRANSITIONS.get(current, set())
        for target in QueueStatus:
            if target in allowed_targets:
                assert can_transition(current, target) is True
                assert transition_token(current, target) == target
            else:
                assert can_transition(current, target) is False
                with pytest.raises(InvalidStateTransitionError):
                    transition_token(current, target)
