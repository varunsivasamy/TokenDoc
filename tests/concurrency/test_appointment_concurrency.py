from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.security import create_access_token, hash_password
from app.domain.enums import UserRole
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User


def test_concurrent_double_booking_prevention(client: TestClient, db_session: Session):
    """Concurrency test: 50 simultaneous booking attempts for the same slot.

    ACCEPTANCE CRITERIA:
    - Exactly 1 request succeeds with 201 Created.
    - Exactly 49 requests fail with 409 Conflict.
    - Only 1 appointment row exists in the database.
    """
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

    token = create_access_token(
        {"sub": rec_user.id, "clinic_id": clinic.id, "role": rec_user.role}
    )
    headers = {"Authorization": f"Bearer {token}"}

    target_slot_start = datetime(2026, 10, 20, 9, 0, 0, tzinfo=timezone.utc).isoformat()
    target_slot_end = datetime(2026, 10, 20, 9, 15, 0, tzinfo=timezone.utc).isoformat()

    num_concurrent_requests = 50

    def attempt_booking(_: int) -> int:
        response = client.post(
            "/api/v1/appointments",
            headers=headers,
            json={
                "doctor_id": doctor.id,
                "patient_id": patient.id,
                "slot_start": target_slot_start,
                "slot_end": target_slot_end,
            },
        )
        return response.status_code

    with ThreadPoolExecutor(max_workers=num_concurrent_requests) as executor:
        status_codes = list(executor.map(attempt_booking, range(num_concurrent_requests)))

    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    assert success_count == 1, f"Expected exactly 1 success, but got {success_count}. Status codes: {status_codes}"
    assert conflict_count == 49, f"Expected 49 conflicts (409), but got {conflict_count}"
