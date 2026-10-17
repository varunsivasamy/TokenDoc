from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domain.enums import UserRole
from app.models.clinic import Clinic
from app.models.user import User


def test_cross_tenant_data_isolation(client: TestClient, db_session: Session):
    """Rigorous security test: User in Clinic A must never read Clinic B's records."""
    # 1. Setup two distinct clinic tenants
    clinic_a = Clinic(id="clinic-alpha", name="Alpha Health", slug="alpha-health")
    clinic_b = Clinic(id="clinic-beta", name="Beta Care", slug="beta-care")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    # 2. Setup user accounts in each clinic
    user_a = User(
        id="user-alpha-doc",
        clinic_id=clinic_a.id,
        email="doctor@alpha.com",
        full_name="Dr. Alpha",
        hashed_password=hash_password("PassAlpha123!"),
        role=UserRole.DOCTOR,
        is_active=True,
    )
    user_b = User(
        id="user-beta-doc",
        clinic_id=clinic_b.id,
        email="doctor@beta.com",
        full_name="Dr. Beta",
        hashed_password=hash_password("PassBeta123!"),
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()

    token_a = create_access_token({"sub": user_a.id, "clinic_id": clinic_a.id, "role": user_a.role})
    token_b = create_access_token({"sub": user_b.id, "clinic_id": clinic_b.id, "role": user_b.role})

    # 3. User A lists users -> only Alpha users visible
    res_a = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    user_ids_seen_by_a = [u["id"] for u in res_a.json()]
    assert user_a.id in user_ids_seen_by_a
    assert user_b.id not in user_ids_seen_by_a

    # 4. User B lists users -> only Beta users visible
    res_b = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    user_ids_seen_by_b = [u["id"] for u in res_b.json()]
    assert user_b.id in user_ids_seen_by_b
    assert user_a.id not in user_ids_seen_by_b

    # 5. User A directly requests User B's record by UUID -> must return 404 Not Found
    direct_res_a = client.get(
        f"/api/v1/auth/users/{user_b.id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert direct_res_a.status_code == 404
    assert direct_res_a.json()["detail"] == "User not found"

    # 6. User B directly requests User A's record by UUID -> must return 404 Not Found
    direct_res_b = client.get(
        f"/api/v1/auth/users/{user_a.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert direct_res_b.status_code == 404
    assert direct_res_b.json()["detail"] == "User not found"
