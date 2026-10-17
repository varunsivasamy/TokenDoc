from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domain.enums import UserRole
from app.models.clinic import Clinic
from app.models.user import User


def test_patient_crud_duplicate_phone_and_search(
    client: TestClient, db_session: Session, sample_clinic: Clinic
):
    """Test patient registration, duplicate phone prevention, and search with pagination."""
    rec_user = User(
        id="user-rec-patient-test",
        clinic_id=sample_clinic.id,
        email="reception@apexclinic.com",
        full_name="Front Desk Staff",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    db_session.add(rec_user)
    db_session.commit()

    token = create_access_token(
        {"sub": rec_user.id, "clinic_id": sample_clinic.id, "role": rec_user.role}
    )
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Patient 1
    p1_res = client.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "full_name": "Alice Walker",
            "phone": "+1-555-0101",
            "email": "alice@example.com",
            "date_of_birth": "1990-05-15",
            "gender": "Female",
            "medical_record_number": "MRN-1001",
        },
    )
    assert p1_res.status_code == 201
    p1_data = p1_res.json()
    assert p1_data["full_name"] == "Alice Walker"
    p1_id = p1_data["id"]

    # 2. Attempt duplicate phone registration -> 409 Conflict
    dup_res = client.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "full_name": "Alice Duplicate",
            "phone": "+1-555-0101",
            "medical_record_number": "MRN-1002",
        },
    )
    assert dup_res.status_code == 409
    assert "already registered" in dup_res.json()["detail"]

    # 3. Create Patient 2
    client.post(
        "/api/v1/patients",
        headers=headers,
        json={
            "full_name": "Bob Builder",
            "phone": "+1-555-0102",
            "date_of_birth": "1985-08-20",
            "medical_record_number": "MRN-1003",
        },
    )

    # 4. Search by name query
    search_name = client.get("/api/v1/patients/search?q=Alice", headers=headers)
    assert search_name.status_code == 200
    results = search_name.json()
    assert len(results) == 1
    assert results[0]["full_name"] == "Alice Walker"

    # 5. Search by phone prefix
    search_phone = client.get("/api/v1/patients/search?q=555-0102", headers=headers)
    assert search_phone.status_code == 200
    assert len(search_phone.json()) == 1
    assert search_phone.json()[0]["full_name"] == "Bob Builder"

    # 6. Search by MRN
    search_mrn = client.get("/api/v1/patients/search?q=MRN-1001", headers=headers)
    assert search_mrn.status_code == 200
    assert len(search_mrn.json()) == 1

    # 7. Get by ID
    get_res = client.get(f"/api/v1/patients/{p1_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["phone"] == "+1-555-0101"

    # 8. Update patient
    patch_res = client.patch(
        f"/api/v1/patients/{p1_id}",
        headers=headers,
        json={"email": "alice.updated@example.com"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["email"] == "alice.updated@example.com"


def test_patients_and_doctors_tenant_isolation(client: TestClient, db_session: Session):
    """Verify that Clinic A users cannot read Clinic B's doctors or patients."""
    clinic_a = Clinic(id="clinic-iso-a", name="Clinic A", slug="clinic-iso-a")
    clinic_b = Clinic(id="clinic-iso-b", name="Clinic B", slug="clinic-iso-b")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    rec_a = User(
        id="user-rec-iso-a",
        clinic_id=clinic_a.id,
        email="reception@a.com",
        full_name="Staff A",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    rec_b = User(
        id="user-rec-iso-b",
        clinic_id=clinic_b.id,
        email="reception@b.com",
        full_name="Staff B",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    db_session.add_all([rec_a, rec_b])
    db_session.commit()

    token_a = create_access_token({"sub": rec_a.id, "clinic_id": clinic_a.id, "role": rec_a.role})
    token_b = create_access_token({"sub": rec_b.id, "clinic_id": clinic_b.id, "role": rec_b.role})

    # Register patient in Clinic A
    create_res = client.post(
        "/api/v1/patients",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "full_name": "Secret Patient A",
            "phone": "+1-999-0001",
            "medical_record_number": "MRN-A-1",
        },
    )
    assert create_res.status_code == 201
    patient_a_id = create_res.json()["id"]

    # Clinic B staff querying patient A by ID -> 404 Not Found
    b_get_res = client.get(
        f"/api/v1/patients/{patient_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert b_get_res.status_code == 404

    # Clinic B staff searching for patient A -> 0 results
    b_search_res = client.get(
        "/api/v1/patients/search?q=Secret",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert b_search_res.status_code == 200
    assert len(b_search_res.json()) == 0
