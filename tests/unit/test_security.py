from datetime import timedelta
import pytest
from jose import jwt
from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hashing_and_verification():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_create_and_decode_access_token():
    payload = {
        "sub": "user-uuid-1234",
        "clinic_id": "clinic-uuid-5678",
        "role": "DOCTOR",
    }
    token = create_access_token(payload, expires_delta=timedelta(minutes=15))
    decoded = decode_access_token(token)

    assert decoded["sub"] == "user-uuid-1234"
    assert decoded["clinic_id"] == "clinic-uuid-5678"
    assert decoded["role"] == "DOCTOR"
    assert "exp" in decoded


def test_expired_token_raises_error():
    payload = {"sub": "user-uuid-1234"}
    # Token expired 10 minutes ago
    expired_token = create_access_token(payload, expires_delta=timedelta(minutes=-10))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired_token)
