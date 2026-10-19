import secrets
from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy import desc, select, text
from sqlalchemy.orm import Session

from app.models.queue_token import QueueToken
from app.repositories.base_repository import BaseTenantRepository


class TokenRepository(BaseTenantRepository[QueueToken]):
    """Tenant-scoped repository for QueueToken entities and atomic daily sequence numbering."""

    def __init__(self, db: Session, clinic_id: str):
        super().__init__(QueueToken, db, clinic_id)

    def get_next_token_number_atomic(self, doctor_id: str, token_date: date) -> int:
        """Atomically increment and return the next sequential token number for doctor and date.

        Uses atomic UPSERT with RETURNING to guarantee gap-free, concurrency-safe sequences
        without MAX()+1 or race conditions.
        """
        now = datetime.now(UTC)
        cnt_id = f"cnt_{secrets.token_hex(8)}"

        stmt = text("""
            INSERT INTO daily_token_counters (id, clinic_id, doctor_id, token_date, last_number, created_at, updated_at)
            VALUES (:id, :clinic_id, :doctor_id, :token_date, 1, :created_at, :updated_at)
            ON CONFLICT (doctor_id, token_date)
            DO UPDATE SET
                last_number = daily_token_counters.last_number + 1,
                updated_at = :updated_at
            RETURNING last_number;
        """)

        result = self._db.execute(
            stmt,
            {
                "id": cnt_id,
                "clinic_id": self._clinic_id,
                "doctor_id": doctor_id,
                "token_date": token_date,
                "created_at": now,
                "updated_at": now,
            },
        )
        row = result.fetchone()
        self._db.commit()
        return int(row[0])

    def get_by_access_code(self, access_code: str) -> QueueToken | None:
        """Find queue token by public access code (bypasses tenant scope for public patient lookup)."""
        stmt = select(QueueToken).where(QueueToken.access_code == access_code)
        return self._db.scalars(stmt).first()

    def list_active_tokens_for_doctor(
        self, doctor_id: str, token_date: date
    ) -> Sequence[QueueToken]:
        """List active tokens (WAITING, CALLED, IN_CONSULTATION) for a doctor on a date."""
        stmt = (
            self._scoped_query()
            .where(
                QueueToken.doctor_id == doctor_id,
                QueueToken.token_date == token_date,
            )
            .order_by(QueueToken.token_number)
        )
        return self._db.scalars(stmt).all()

    def get_latest_token_for_patient_today(
        self, patient_id: str, doctor_id: str, token_date: date
    ) -> QueueToken | None:
        """Check if patient already has a token for this doctor today."""
        stmt = (
            self._scoped_query()
            .where(
                QueueToken.patient_id == patient_id,
                QueueToken.doctor_id == doctor_id,
                QueueToken.token_date == token_date,
            )
            .order_by(desc(QueueToken.token_number))
        )
        return self._db.scalars(stmt).first()
