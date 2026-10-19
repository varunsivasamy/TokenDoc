import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.domain.enums import UserRole
from app.main import app
from app.models.base import Base
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.queue_token import DailyTokenCounter, QueueToken
from app.models.user import User

CONC_QUEUE_DB_PATH = "./test_queue_concurrency.db"
CONC_QUEUE_DATABASE_URL = f"sqlite:///{CONC_QUEUE_DB_PATH}"


@pytest.fixture
def queue_concurrency_db():
    """Setup isolated file-based SQLite database with NullPool for 100-thread queue concurrency testing."""
    if os.path.exists(CONC_QUEUE_DB_PATH):
        try:
            os.remove(CONC_QUEUE_DB_PATH)
        except OSError:
            pass

    conc_engine = create_engine(
        CONC_QUEUE_DATABASE_URL,
        connect_args={"timeout": 60.0, "check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(bind=conc_engine)
    ConcSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=conc_engine)

    def override_get_db():
        session = ConcSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    session = ConcSessionLocal()
    try:
        yield session, conc_engine
    finally:
        session.close()
        app.dependency_overrides.clear()
        conc_engine.dispose()
        if os.path.exists(CONC_QUEUE_DB_PATH):
            try:
                os.remove(CONC_QUEUE_DB_PATH)
            except OSError:
                pass


def test_concurrent_100_walkin_tokens_unique_and_gap_free(queue_concurrency_db):
    """Concurrency test: 100 simultaneous walk-in token issuance requests.

    ACCEPTANCE CRITERIA:
    - 100 parallel walk-ins produce 100 unique, gap-free numbers: {1, 2, 3, ..., 100}.
    - No race condition or duplicates.
    - Token counter reflects exactly 100.
    """
    db_session, _ = queue_concurrency_db

    # Setup tenant, doctor, receptionist, and 100 patients
    clinic = Clinic(id="clinic-q-conc-1", name="Queue Concurrency Clinic", slug="queue-conc-clinic")
    db_session.add(clinic)
    db_session.commit()

    rec_user = User(
        id="user-rec-q-conc",
        clinic_id=clinic.id,
        email="q-conc-rec@clinic.com",
        full_name="Queue Staff",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    doctor = Doctor(
        id="doc-q-conc-1",
        clinic_id=clinic.id,
        full_name="Dr. HighThroughput",
        specialty="Pediatrics",
        default_slot_duration_minutes=15,
    )
    db_session.add_all([rec_user, doctor])
    db_session.commit()

    patients = [
        Patient(
            id=f"pat-q-conc-{i}",
            clinic_id=clinic.id,
            full_name=f"Patient {i}",
            phone=f"+1-555-{1000 + i}",
            medical_record_number=f"MRN-Q-{i}",
        )
        for i in range(100)
    ]
    db_session.add_all(patients)
    db_session.commit()

    token = create_access_token({"sub": rec_user.id, "clinic_id": clinic.id, "role": rec_user.role})
    headers = {"Authorization": f"Bearer {token}"}

    doc_id = str(doctor.id)
    pat_ids = [str(p.id) for p in patients]

    num_concurrent_requests = 100

    def issue_walkin_token(idx: int) -> dict:
        with TestClient(app) as thread_client:
            response = thread_client.post(
                "/api/v1/queue/tokens",
                headers=headers,
                json={
                    "doctor_id": doc_id,
                    "patient_id": pat_ids[idx],
                    "is_emergency": False,
                },
            )
            return {
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 201 else None,
                "text": response.text if response.status_code != 201 else None,
            }

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(issue_walkin_token, range(num_concurrent_requests)))

    # Verify all requests succeeded
    failed_requests = [r for r in results if r["status_code"] != 201]
    assert len(failed_requests) == 0, f"Some requests failed: {failed_requests}"

    token_numbers = [r["data"]["token_number"] for r in results]
    assert len(token_numbers) == 100

    # Verify 100 unique, gap-free numbers: 1 to 100
    sorted_numbers = sorted(token_numbers)
    expected_numbers = list(range(1, 101))
    assert sorted_numbers == expected_numbers, f"Numbers were not gap-free 1..100: {sorted_numbers}"

    # Verify database state
    db_tokens = (
        db_session.query(QueueToken)
        .filter(QueueToken.doctor_id == doc_id)
        .order_by(QueueToken.token_number)
        .all()
    )
    assert len(db_tokens) == 100
    assert [t.token_number for t in db_tokens] == expected_numbers

    # Verify counter table
    today = datetime.now(UTC).date()
    counter = (
        db_session.query(DailyTokenCounter)
        .filter(
            DailyTokenCounter.doctor_id == doc_id,
            DailyTokenCounter.token_date == today,
        )
        .first()
    )
    assert counter is not None
    assert counter.last_number == 100
