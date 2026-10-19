from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domain.enums import AppointmentStatus, UserRole
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User


def test_appointment_booking_cancellation_and_slot_reuse(
    client: TestClient, db_session: Session, sample_clinic: Clinic
):
    """Test full booking, cancellation, and slot reuse cycle enabled by the partial unique index."""
    rec = User(
        id="u-rec-appt",
        clinic_id=sample_clinic.id,
        email="rec-appt@clinic.com",
        full_name="Appt Staff",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    doctor = Doctor(
        id="doc-appt-1",
        clinic_id=sample_clinic.id,
        full_name="Dr. Slot",
        specialty="Pediatrics",
    )
    patient = Patient(
        id="pat-appt-1",
        clinic_id=sample_clinic.id,
        full_name="Patient One",
        phone="+1-555-4001",
        medical_record_number="MRN-APPT-1",
    )
    patient2 = Patient(
        id="pat-appt-2",
        clinic_id=sample_clinic.id,
        full_name="Patient Two",
        phone="+1-555-4002",
        medical_record_number="MRN-APPT-2",
    )
    db_session.add_all([rec, doctor, patient, patient2])
    db_session.commit()

    token = create_access_token({"sub": rec.id, "clinic_id": sample_clinic.id, "role": rec.role})
    headers = {"Authorization": f"Bearer {token}"}

    slot1_start = datetime(2026, 10, 25, 10, 0, 0, tzinfo=UTC).isoformat()
    slot1_end = datetime(2026, 10, 25, 10, 15, 0, tzinfo=UTC).isoformat()

    # 1. Book initial appointment
    res1 = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "doctor_id": doctor.id,
            "patient_id": patient.id,
            "slot_start": slot1_start,
            "slot_end": slot1_end,
        },
    )
    assert res1.status_code == 201
    appt1_data = res1.json()
    assert appt1_data["status"] == AppointmentStatus.BOOKED.value
    appt1_id = appt1_data["id"]

    # 2. Duplicate booking for same slot -> 409 Conflict
    dup_res = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "doctor_id": doctor.id,
            "patient_id": patient2.id,
            "slot_start": slot1_start,
            "slot_end": slot1_end,
        },
    )
    assert dup_res.status_code == 409
    assert "already been booked" in dup_res.json()["detail"]

    # 3. Cancel the first appointment
    cancel_res = client.post(f"/api/v1/appointments/{appt1_id}/cancel", headers=headers)
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == AppointmentStatus.CANCELLED.value

    # 4. Now Patient 2 can book the newly freed slot (verifies partial index behaviour)
    reuse_res = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "doctor_id": doctor.id,
            "patient_id": patient2.id,
            "slot_start": slot1_start,
            "slot_end": slot1_end,
        },
    )
    assert reuse_res.status_code == 201
    assert reuse_res.json()["status"] == AppointmentStatus.BOOKED.value


def test_appointment_reschedule(client: TestClient, db_session: Session, sample_clinic: Clinic):
    """Test rescheduling an appointment to a new open slot and conflicting slot."""
    rec = User(
        id="u-rec-resched",
        clinic_id=sample_clinic.id,
        email="rec-resched@clinic.com",
        full_name="Resched Staff",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    doctor = Doctor(
        id="doc-resched-1",
        clinic_id=sample_clinic.id,
        full_name="Dr. Calendar",
        specialty="Surgery",
    )
    patient = Patient(
        id="pat-resched-1",
        clinic_id=sample_clinic.id,
        full_name="Patient Mover",
        phone="+1-555-5001",
        medical_record_number="MRN-RESCHED-1",
    )
    db_session.add_all([rec, doctor, patient])
    db_session.commit()

    token = create_access_token({"sub": rec.id, "clinic_id": sample_clinic.id, "role": rec.role})
    headers = {"Authorization": f"Bearer {token}"}

    slot_a = datetime(2026, 10, 26, 14, 0, 0, tzinfo=UTC).isoformat()
    slot_a_end = datetime(2026, 10, 26, 14, 15, 0, tzinfo=UTC).isoformat()

    slot_b = datetime(2026, 10, 26, 15, 0, 0, tzinfo=UTC).isoformat()
    slot_b_end = datetime(2026, 10, 26, 15, 15, 0, tzinfo=UTC).isoformat()

    # Book slot A
    book_res = client.post(
        "/api/v1/appointments",
        headers=headers,
        json={
            "doctor_id": doctor.id,
            "patient_id": patient.id,
            "slot_start": slot_a,
            "slot_end": slot_a_end,
        },
    )
    assert book_res.status_code == 201
    appt_id = book_res.json()["id"]

    # Reschedule to slot B -> 200 OK
    resched_res = client.post(
        f"/api/v1/appointments/{appt_id}/reschedule",
        headers=headers,
        json={
            "new_slot_start": slot_b,
            "new_slot_end": slot_b_end,
        },
    )
    assert resched_res.status_code == 200
    assert resched_res.json()["slot_start"].startswith("2026-10-26T15:00:00")
