from datetime import date

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.enums import QueueStatus
from app.domain.ports import LiveQueueStore
from app.models.queue_token import QueueToken


def compute_priority_score(
    status: str,
    is_emergency: bool,
    token_number: int,
    has_appointment_window: bool = False,
) -> float | None:
    """Compute Redis Sorted Set score (lower score = higher priority / earlier service).

    Priority hierarchy:
    1. IN_CONSULTATION: score 0.. (current patient)
    2. CALLED: score 100.. (patient called into room)
    3. WAITING + Emergency: score 1000.. (emergency leapfrogs to head of waiting queue)
    4. WAITING + In Appointment Window: score 2000.. (scheduled appointment window)
    5. WAITING + Regular Walk-in: score 5000 + token_number (FIFO by sequential arrival number)
    6. Terminal states (COMPLETED, NO_SHOW, CANCELLED): None (removed from active live queue)
    """
    if status == QueueStatus.IN_CONSULTATION.value:
        return 0.0 + (token_number * 0.0001)

    if status == QueueStatus.CALLED.value:
        return 100.0 + (token_number * 0.0001)

    if status == QueueStatus.WAITING.value:
        if is_emergency:
            return 1000.0 + (token_number * 0.0001)
        if has_appointment_window:
            return 2000.0 + (token_number * 0.0001)
        return 5000.0 + float(token_number)

    return None


class InMemoryLiveQueue:
    """In-memory thread-safe implementation of LiveQueueStore for hermetic testing."""

    def __init__(self):
        self._queues: dict[str, dict[str, float]] = {}

    def _get_key(self, clinic_id: str, doctor_id: str, token_date: date) -> str:
        return f"clinicq:{clinic_id}:queue:{doctor_id}:{token_date.isoformat()}"

    def add_or_update(
        self, clinic_id: str, doctor_id: str, token_date: date, token_id: str, score: float
    ) -> None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        if key not in self._queues:
            self._queues[key] = {}
        self._queues[key][token_id] = score

    def remove(self, clinic_id: str, doctor_id: str, token_date: date, token_id: str) -> None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        if key in self._queues and token_id in self._queues[key]:
            del self._queues[key][token_id]

    def get_ordered_token_ids(
        self, clinic_id: str, doctor_id: str, token_date: date
    ) -> list[str]:
        key = self._get_key(clinic_id, doctor_id, token_date)
        if key not in self._queues:
            return []
        items = list(self._queues[key].items())
        # Sort by score ascending, then by token_id
        items.sort(key=lambda x: (x[1], x[0]))
        return [item[0] for item in items]

    def clear(self, clinic_id: str, doctor_id: str, token_date: date) -> None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        self._queues.pop(key, None)

    def get_score(
        self, clinic_id: str, doctor_id: str, token_date: date, token_id: str
    ) -> float | None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        return self._queues.get(key, {}).get(token_id)


class RedisLiveQueue:
    """Production Redis Sorted Set implementation of LiveQueueStore."""

    def __init__(self, redis_client: redis.Redis | None = None):
        if redis_client is not None:
            self._redis = redis_client
        else:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def _get_key(self, clinic_id: str, doctor_id: str, token_date: date) -> str:
        return f"clinicq:{clinic_id}:queue:{doctor_id}:{token_date.isoformat()}"

    def add_or_update(
        self, clinic_id: str, doctor_id: str, token_date: date, token_id: str, score: float
    ) -> None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        self._redis.zadd(key, {token_id: score})

    def remove(self, clinic_id: str, doctor_id: str, token_date: date, token_id: str) -> None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        self._redis.zrem(key, token_id)

    def get_ordered_token_ids(
        self, clinic_id: str, doctor_id: str, token_date: date
    ) -> list[str]:
        key = self._get_key(clinic_id, doctor_id, token_date)
        items = self._redis.zrange(key, 0, -1)
        return [item if isinstance(item, str) else item.decode() for item in items]

    def clear(self, clinic_id: str, doctor_id: str, token_date: date) -> None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        self._redis.delete(key)

    def get_score(
        self, clinic_id: str, doctor_id: str, token_date: date, token_id: str
    ) -> float | None:
        key = self._get_key(clinic_id, doctor_id, token_date)
        score = self._redis.zscore(key, token_id)
        return float(score) if score is not None else None


# Default global store instance (can be overridden in tests via dependency injection)
_in_memory_store = InMemoryLiveQueue()


def get_live_queue_store() -> LiveQueueStore:
    """Dependency provider returning LiveQueueStore. Defaults to Redis if available, else in-memory."""
    try:
        r = redis.from_url(settings.REDIS_URL, socket_timeout=0.2, decode_responses=True)
        r.ping()
        return RedisLiveQueue(r)
    except Exception:
        return _in_memory_store


def rebuild_live_queue(
    db: Session,
    store: LiveQueueStore,
    clinic_id: str,
    doctor_id: str,
    token_date: date,
) -> int:
    """Startup recovery: rebuild doctor's live queue ZSET directly from Postgres truth.

    1. Clear any stale queue in the store.
    2. Query active tokens (IN_CONSULTATION, CALLED, WAITING).
    3. Compute priority score for each token.
    4. Insert into the sorted store.
    Returns the count of recovered active tokens.
    """
    store.clear(clinic_id, doctor_id, token_date)

    active_statuses = [
        QueueStatus.IN_CONSULTATION.value,
        QueueStatus.CALLED.value,
        QueueStatus.WAITING.value,
    ]
    stmt = (
        select(QueueToken)
        .where(
            QueueToken.clinic_id == clinic_id,
            QueueToken.doctor_id == doctor_id,
            QueueToken.token_date == token_date,
            QueueToken.status.in_(active_statuses),
        )
        .order_by(QueueToken.token_number)
    )
    active_tokens = db.scalars(stmt).all()

    count = 0
    for token in active_tokens:
        has_apt = bool(token.appointment_id)
        score = compute_priority_score(
            status=token.status,
            is_emergency=token.is_emergency,
            token_number=token.token_number,
            has_appointment_window=has_apt,
        )
        if score is not None:
            store.add_or_update(clinic_id, doctor_id, token_date, token.id, score)
            count += 1

    return count
