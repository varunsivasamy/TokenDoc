from sqlalchemy.orm import Session

from app.models.clinic import Clinic
from app.models.user import User
from app.repositories.base_repository import BaseTenantRepository


def test_base_tenant_repository_isolation(db_session: Session):
    """Verify that BaseTenantRepository strictly restricts reads, updates, and deletes to tenant."""
    clinic_a = Clinic(id="clinic-a", name="Clinic A", slug="clinic-a")
    clinic_b = Clinic(id="clinic-b", name="Clinic B", slug="clinic-b")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    repo_a = BaseTenantRepository[User](User, db_session, clinic_id="clinic-a")
    repo_b = BaseTenantRepository[User](User, db_session, clinic_id="clinic-b")

    # Create user under Clinic A
    user_a = User(
        id="user-a-1",
        email="a1@clinica.com",
        full_name="User A1",
        hashed_password="hash",
    )
    repo_a.create(user_a)

    # Verify user_a has clinic_id set to clinic-a
    assert user_a.clinic_id == "clinic-a"

    # Clinic A repo can find user_a
    found_a = repo_a.get_by_id("user-a-1")
    assert found_a is not None
    assert found_a.id == "user-a-1"

    # Clinic B repo CANNOT find user_a (returns None)
    found_b = repo_b.get_by_id("user-a-1")
    assert found_b is None

    # Clinic B listing contains 0 items
    assert len(repo_b.list_all()) == 0

    # Clinic B attempting to delete user_a returns False (does not delete)
    deleted = repo_b.delete_by_id("user-a-1")
    assert deleted is False
    assert repo_a.get_by_id("user-a-1") is not None
