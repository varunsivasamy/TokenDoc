from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domain.enums import UserRole
from app.models.clinic import Clinic
from app.models.user import User


def test_doctor_crud_and_role_permissions(
    client: TestClient, db_session: Session, sample_clinic: Clinic
):
    """Test doctor creation by admin, listing, and permission restrictions for receptionist."""
    # 1. Create clinic admin and receptionist
    admin_user = User(
        id="user-admin-1",
        clinic_id=sample_clinic.id,
        email="admin@apexclinic.com",
        full_name="Admin Boss",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.CLINIC_ADMIN,
        is_active=True,
    )
    rec_user = User(
        id="user-rec-1",
        clinic_id=sample_clinic.id,
        email="rec@apexclinic.com",
        full_name="Front Desk",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    db_session.add_all([admin_user, rec_user])
    db_session.commit()

    admin_token = create_access_token(
        {"sub": admin_user.id, "clinic_id": sample_clinic.id, "role": admin_user.role}
    )
    rec_token = create_access_token(
        {"sub": rec_user.id, "clinic_id": sample_clinic.id, "role": rec_user.role}
    )

    # 2. Receptionist attempts to create doctor -> 403 Forbidden
    rec_create_res = client.post(
        "/api/v1/doctors",
        headers={"Authorization": f"Bearer {rec_token}"},
        json={
            "full_name": "Dr. Gregory House",
            "specialty": "Diagnostic Medicine",
            "room_number": "Room 101",
            "default_slot_duration_minutes": 20,
        },
    )
    assert rec_create_res.status_code == 403

    # 3. Clinic Admin creates doctor -> 201 Created
    admin_create_res = client.post(
        "/api/v1/doctors",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "full_name": "Dr. Gregory House",
            "specialty": "Diagnostic Medicine",
            "room_number": "Room 101",
            "default_slot_duration_minutes": 20,
        },
    )
    assert admin_create_res.status_code == 201
    doctor_data = admin_create_res.json()
    assert doctor_data["full_name"] == "Dr. Gregory House"
    assert doctor_data["clinic_id"] == sample_clinic.id
    doc_id = doctor_data["id"]

    # 4. Receptionist can view doctors list
    list_res = client.get(
        "/api/v1/doctors",
        headers={"Authorization": f"Bearer {rec_token}"},
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 5. Get doctor by ID
    get_res = client.get(
        f"/api/v1/doctors/{doc_id}",
        headers={"Authorization": f"Bearer {rec_token}"},
    )
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id

    # 6. Admin updates doctor
    patch_res = client.patch(
        f"/api/v1/doctors/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"room_number": "Room 202"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["room_number"] == "Room 202"
