from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domain.enums import UserRole
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User


def test_doctor_and_patient_validation_failures(
    client: TestClient, db_session: Session, sample_clinic: Clinic
):
    """Verify validation errors (422) on bad inputs for doctor and patient endpoints."""
    admin = User(
        id="user-admin-val",
        clinic_id=sample_clinic.id,
        email="admin-val@clinic.com",
        full_name="Admin Val",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.CLINIC_ADMIN,
        is_active=True,
    )
    rec = User(
        id="user-rec-val",
        clinic_id=sample_clinic.id,
        email="rec-val@clinic.com",
        full_name="Rec Val",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    db_session.add_all([admin, rec])
    db_session.commit()

    admin_token = create_access_token(
        {"sub": admin.id, "clinic_id": sample_clinic.id, "role": admin.role}
    )
    rec_token = create_access_token(
        {"sub": rec.id, "clinic_id": sample_clinic.id, "role": rec.role}
    )

    # Doctor slot duration out of range (< 5 mins) -> 422
    bad_doc_res = client.post(
        "/api/v1/doctors",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": "Dr. Fast",
            "default_slot_duration_minutes": 2,
        },
    )
    assert bad_doc_res.status_code == 422

    # Patient name too short (< 2 chars) -> 422
    bad_pat_res = client.post(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={
            "full_name": "A",
            "phone": "+1-555-1111",
            "medical_record_number": "MRN-1",
        },
    )
    assert bad_pat_res.status_code == 422

    # Patient phone too short (< 5 chars) -> 422
    bad_phone_res = client.post(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={
            "full_name": "John Doe",
            "phone": "123",
            "medical_record_number": "MRN-2",
        },
    )
    assert bad_phone_res.status_code == 422


def test_cross_tenant_update_and_delete_prevention(client: TestClient, db_session: Session):
    """Verify that Clinic A cannot update Clinic B's doctors or patients."""
    clinic_a = Clinic(id="c-alpha-val", name="Clinic Alpha", slug="c-alpha-val")
    clinic_b = Clinic(id="c-beta-val", name="Clinic Beta", slug="c-beta-val")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    admin_a = User(
        id="u-admin-a-val",
        clinic_id=clinic_a.id,
        email="admin@alpha-val.com",
        full_name="Admin A",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.CLINIC_ADMIN,
        is_active=True,
    )
    db_session.add(admin_a)

    doc_b = Doctor(
        id="doc-beta-val",
        clinic_id=clinic_b.id,
        full_name="Dr. Beta",
        specialty="Pediatrics",
        room_number="Room B",
    )
    pat_b = Patient(
        id="pat-beta-val",
        clinic_id=clinic_b.id,
        full_name="Patient Beta",
        phone="+1-555-9999",
        medical_record_number="MRN-B-1",
    )
    db_session.add_all([doc_b, pat_b])
    db_session.commit()

    token_a = create_access_token(
        {"sub": admin_a.id, "clinic_id": clinic_a.id, "role": admin_a.role}
    )

    # Clinic A attempts to update Doctor in Clinic B -> 404 Not Found
    patch_doc = client.patch(
        f"/api/v1/doctors/{doc_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"room_number": "Room Compromised"},
    )
    assert patch_doc.status_code == 404
    assert patch_doc.json()["detail"] == "Doctor not found"

    # Clinic A attempts to update Patient in Clinic B -> 404 Not Found
    patch_pat = client.patch(
        f"/api/v1/patients/{pat_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"full_name": "Tampered Name"},
    )
    assert patch_pat.status_code == 404
    assert patch_pat.json()["detail"] == "Patient not found"
