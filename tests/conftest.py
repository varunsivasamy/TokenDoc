from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import hash_password
from app.domain.enums import UserRole
from app.main import app
from app.models.base import Base
from app.models.clinic import Clinic
from app.models.user import User

# In-memory SQLite engine for fast, isolated tests
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all database tables in memory once for the test session."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session per test, rolling back on completion."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient configured with database session dependency override."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_clinic(db_session: Session) -> Clinic:
    """Fixture providing a persisted sample clinic."""
    clinic = Clinic(
        id="clinic-aaa-111",
        name="Apex Health Clinic",
        slug="apex-health",
        timezone="UTC",
    )
    db_session.add(clinic)
    db_session.commit()
    db_session.refresh(clinic)
    return clinic


@pytest.fixture
def sample_user(db_session: Session, sample_clinic: Clinic) -> User:
    """Fixture providing a persisted test user."""
    user = User(
        id="user-aaa-111",
        clinic_id=sample_clinic.id,
        email="doctor@apexclinic.com",
        hashed_password=hash_password("DoctorSecret123!"),
        full_name="Dr. Sarah Adams",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
