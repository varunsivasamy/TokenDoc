from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domain.enums import UserRole
from app.models.clinic import Clinic
from app.models.user import User


def test_get_current_user_me_endpoint_success(
    client: TestClient, sample_clinic: Clinic, sample_user: User
):
    """Verify that a valid bearer token authenticates successfully to /auth/me."""
    token = create_access_token(
        {"sub": sample_user.id, "clinic_id": sample_clinic.id, "role": sample_user.role}
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_user.id
    assert data["email"] == sample_user.email
    assert data["role"] == "DOCTOR"


def test_get_current_user_invalid_token(client: TestClient):
    """Verify that an invalid token returns 401 Unauthorized."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


def test_get_current_user_missing_token(client: TestClient):
    """Verify that missing Authorization header returns 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_require_role_doctor_allowed(client: TestClient, sample_clinic: Clinic, sample_user: User):
    """Verify that DOCTOR user can access doctor-protected endpoint."""
    token = create_access_token(
        {"sub": sample_user.id, "clinic_id": sample_clinic.id, "role": sample_user.role}
    )

    response = client.get(
        "/api/v1/auth/doctor-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Doctor access granted"


def test_require_role_receptionist_forbidden(
    client: TestClient, db_session: Session, sample_clinic: Clinic
):
    """Verify that RECEPTIONIST user is rejected with 403 Forbidden from doctor endpoint."""
    receptionist = User(
        id="user-rec-111",
        clinic_id=sample_clinic.id,
        email="receptionist@apexclinic.com",
        hashed_password=hash_password("RecPass123!"),
        full_name="Bob Receptionist",
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    db_session.add(receptionist)
    db_session.commit()

    token = create_access_token(
        {"sub": receptionist.id, "clinic_id": sample_clinic.id, "role": receptionist.role}
    )

    response = client.get(
        "/api/v1/auth/doctor-only",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert "Operation not permitted" in response.json()["detail"]
