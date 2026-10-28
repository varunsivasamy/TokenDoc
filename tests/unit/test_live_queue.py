from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.domain.enums import QueueStatus
from app.models.base import Base
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.queue_token import QueueToken
from app.services.live_queue import (
    InMemoryLiveQueue,
    compute_priority_score,
    rebuild_live_queue,
)


def test_priority_scoring_hierarchy():
    """Verify priority score hierarchy: IN_CONSULTATION < CALLED < Emergency < Appointment < Walk-in."""
    score_in_consult = compute_priority_score(
        status=QueueStatus.IN_CONSULTATION.value,
        is_emergency=False,
        token_number=1,
    )
    score_called = compute_priority_score(
        status=QueueStatus.CALLED.value,
        is_emergency=False,
        token_number=2,
    )
    score_emergency = compute_priority_score(
        status=QueueStatus.WAITING.value,
        is_emergency=True,
        token_number=5,
    )
    score_appointment = compute_priority_score(
        status=QueueStatus.WAITING.value,
        is_emergency=False,
        token_number=3,
        has_appointment_window=True,
    )
    score_walkin_first = compute_priority_score(
        status=QueueStatus.WAITING.value,
        is_emergency=False,
        token_number=1,
    )
    score_walkin_second = compute_priority_score(
        status=QueueStatus.WAITING.value,
        is_emergency=False,
        token_number=2,
    )

    # Assert strict ordering
    assert score_in_consult < score_called
    assert score_called < score_emergency
    assert score_emergency < score_appointment
    assert score_appointment < score_walkin_first
    assert score_walkin_first < score_walkin_second

    # Terminal states return None
    assert compute_priority_score(QueueStatus.COMPLETED.value, False, 1) is None
    assert compute_priority_score(QueueStatus.NO_SHOW.value, False, 1) is None
    assert compute_priority_score(QueueStatus.CANCELLED.value, False, 1) is None


def test_in_memory_live_queue_operations():
    """Test add, order, update, remove, and clear operations in LiveQueueStore."""
    store = InMemoryLiveQueue()
    clinic_id = "test-clinic"
    doctor_id = "test-doc"
    today = date(2026, 10, 20)

    store.add_or_update(clinic_id, doctor_id, today, "token-walkin-1", 5001.0)
    store.add_or_update(clinic_id, doctor_id, today, "token-emergency", 1000.0)
    store.add_or_update(clinic_id, doctor_id, today, "token-called", 100.0)

    # Ordered retrieval: lowest score first
    ordered = store.get_ordered_token_ids(clinic_id, doctor_id, today)
    assert ordered == ["token-called", "token-emergency", "token-walkin-1"]

    # Remove token-called
    store.remove(clinic_id, doctor_id, today, "token-called")
    ordered_after_remove = store.get_ordered_token_ids(clinic_id, doctor_id, today)
    assert ordered_after_remove == ["token-emergency", "token-walkin-1"]

    # Clear queue
    store.clear(clinic_id, doctor_id, today)
    assert store.get_ordered_token_ids(clinic_id, doctor_id, today) == []


def test_rebuild_live_queue_from_postgres():
    """Test startup recovery rebuilding sorted set cache directly from database truth."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    clinic = Clinic(id="clinic-reb-1", name="Rebuild Clinic", slug="rebuild-clinic")
    doctor = Doctor(id="doc-reb-1", clinic_id=clinic.id, full_name="Dr. Rebuild")
    patient1 = Patient(
        id="pat-reb-1",
        clinic_id=clinic.id,
        full_name="Pat One",
        phone="+1-1",
        medical_record_number="MRN-REB-1",
    )
    patient2 = Patient(
        id="pat-reb-2",
        clinic_id=clinic.id,
        full_name="Pat Two",
        phone="+1-2",
        medical_record_number="MRN-REB-2",
    )
    patient3 = Patient(
        id="pat-reb-3",
        clinic_id=clinic.id,
        full_name="Pat Three",
        phone="+1-3",
        medical_record_number="MRN-REB-3",
    )
    session.add_all([clinic, doctor, patient1, patient2, patient3])
    session.commit()

    today = date(2026, 10, 20)
    t1 = QueueToken(
        id="t-walkin",
        clinic_id=clinic.id,
        doctor_id=doctor.id,
        patient_id=patient1.id,
        token_number=1,
        token_date=today,
        status=QueueStatus.WAITING.value,
        is_emergency=False,
    )
    t2 = QueueToken(
        id="t-emergency",
        clinic_id=clinic.id,
        doctor_id=doctor.id,
        patient_id=patient2.id,
        token_number=2,
        token_date=today,
        status=QueueStatus.WAITING.value,
        is_emergency=True,
    )
    t3 = QueueToken(
        id="t-completed",
        clinic_id=clinic.id,
        doctor_id=doctor.id,
        patient_id=patient3.id,
        token_number=3,
        token_date=today,
        status=QueueStatus.COMPLETED.value,
        is_emergency=False,
    )
    session.add_all([t1, t2, t3])
    session.commit()

    store = InMemoryLiveQueue()
    # Rebuild
    recovered_count = rebuild_live_queue(session, store, clinic.id, doctor.id, today)
    assert recovered_count == 2  # Only active (t-emergency and t-walkin), t-completed ignored

    ordered = store.get_ordered_token_ids(clinic.id, doctor.id, today)
    # Emergency should be first
    assert ordered == ["t-emergency", "t-walkin"]

    session.close()
    engine.dispose()
