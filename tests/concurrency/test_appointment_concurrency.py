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
from app.models.appointment import Appointment
from app.models.base import Base
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User

CONC_DB_PATH = "./test_appointment_concurrency.db"
CONC_DATABASE_URL = f"sqlite:///{CONC_DB_PATH}"


@pytest.fixture
def concurrency_db():
    """Setup isolated file-based SQLite database with NullPool for true multi-connection concurrency."""
    if os.path.exists(CONC_DB_PATH):
        try:
            os.remove(CONC_DB_PATH)
        except OSError:
            pass

    conc_engine = create_engine(
        CONC_DATABASE_URL,
        connect_args={"timeout": 30.0, "check_same_thread": False},
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
        if os.path.exists(CONC_DB_PATH):
            try:
                os.remove(CONC_DB_PATH)
            except OSError:
                pass


def test_concurrent_double_booking_prevention(concurrency_db):
    """Concurrency test: 50 simultaneous booking attempts for the same slot.

    ACCEPTANCE CRITERIA:
    - Exactly 1 request succeeds with 201 Created.
    - Exactly 49 requests fail with 409 Conflict.
    - Exactly 1 appointment row exists in the database.
    """
    db_session, conc_engine = concurrency_db

    # 1. Setup tenant, doctor, receptionist, and patient
    clinic = Clinic(id="clinic-conc-1", name="Concurrency Clinic", slug="concurrency-clinic")
    db_session.add(clinic)
    db_session.commit()

    rec_user = User(
        id="user-rec-conc",
        clinic_id=clinic.id,
        email="conc-rec@clinic.com",
        full_name="Conc Staff",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    doctor = Doctor(
        id="doc-conc-1",
        clinic_id=clinic.id,
        full_name="Dr. MultiThread",
        specialty="General",
        default_slot_duration_minutes=15,
    )
    patient = Patient(
        id="pat-conc-1",
        clinic_id=clinic.id,
        full_name="Patient Target",
        phone="+1-555-9000",
        medical_record_number="MRN-CONC",
    )
    db_session.add_all([rec_user, doctor, patient])
    db_session.commit()

    token = create_access_token({"sub": rec_user.id, "clinic_id": clinic.id, "role": rec_user.role})
    headers = {"Authorization": f"Bearer {token}"}

    doc_id = str(doctor.id)
    pat_id = str(patient.id)

    target_slot_start = datetime(2026, 10, 20, 9, 0, 0, tzinfo=UTC).isoformat()
    target_slot_end = datetime(2026, 10, 20, 9, 15, 0, tzinfo=UTC).isoformat()

    num_concurrent_requests = 50

    def attempt_booking(_: int) -> int:
        with TestClient(app) as thread_client:
            response = thread_client.post(
                "/api/v1/appointments",
                headers=headers,
                json={
                    "doctor_id": doc_id,
                    "patient_id": pat_id,
                    "slot_start": target_slot_start,
                    "slot_end": target_slot_end,
                },
            )
            return response.status_code

    with ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
        status_codes = list(executor.map(attempt_booking, range(num_concurrent_requests)))

    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    assert success_count == 1, (
        f"Expected exactly 1 success, but got {success_count}. Status codes: {status_codes}"
    )
    assert conflict_count == 49, f"Expected 49 conflicts (409), but got {conflict_count}"

    # Verify only 1 appointment row exists in DB
    total_appointments = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doc_id,
            Appointment.slot_start == datetime(2026, 10, 20, 9, 0, 0, tzinfo=UTC),
        )
        .count()
    )
    assert total_appointments == 1
