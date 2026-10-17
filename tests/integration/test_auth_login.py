from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.models.clinic import Clinic
from app.models.user import User


def test_login_success(client: TestClient, sample_clinic: Clinic, sample_user: User):
    """Test successful login with correct email and password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@apexclinic.com", "password": "DoctorSecret123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "doctor@apexclinic.com"
    assert data["user"]["role"] == "DOCTOR"
    assert data["user"]["clinic_id"] == sample_clinic.id

    # Verify token decoding
    token_claims = decode_access_token(data["access_token"])
    assert token_claims["sub"] == sample_user.id
    assert token_claims["clinic_id"] == sample_clinic.id
    assert token_claims["role"] == "DOCTOR"


def test_login_wrong_password(client: TestClient, sample_user: User):
    """Test login failure with wrong password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@apexclinic.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_login_nonexistent_email(client: TestClient):
    """Test login failure with email that does not exist."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@apexclinic.com", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401


def test_login_inactive_user(
    client: TestClient, db_session: Session, sample_clinic: Clinic, sample_user: User
):
    """Test that deactivated users cannot log in."""
    sample_user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "doctor@apexclinic.com", "password": "DoctorSecret123!"},
    )
    assert response.status_code == 401
