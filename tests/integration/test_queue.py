import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.domain.enums import QueueStatus, UserRole
from app.models.clinic import Clinic
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.models.user import User


@pytest.fixture
def queue_test_setup(db_session: Session):
    """Seed clinic, receptionist, doctor, and patients for queue testing."""
    clinic_a = Clinic(id="clinic-qa", name="Queue Clinic A", slug="queue-clinic-a")
    clinic_b = Clinic(id="clinic-qb", name="Queue Clinic B", slug="queue-clinic-b")
    db_session.add_all([clinic_a, clinic_b])
    db_session.commit()

    receptionist_a = User(
        id="user-rec-a",
        clinic_id=clinic_a.id,
        email="receptionist@clinica.com",
        full_name="Rec User",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )
    doctor_a = Doctor(
        id="doc-a-1",
        clinic_id=clinic_a.id,
        full_name="Dr. Alpha",
        specialty="General",
    )
    patient_1 = Patient(
        id="pat-a-1",
        clinic_id=clinic_a.id,
        full_name="John Doe",
        phone="+1-555-1111",
        medical_record_number="MRN-QA-1",
    )
    patient_2 = Patient(
        id="pat-a-2",
        clinic_id=clinic_a.id,
        full_name="Jane Smith",
        phone="+1-555-2222",
        medical_record_number="MRN-QA-2",
    )
    patient_3 = Patient(
        id="pat-a-3",
        clinic_id=clinic_a.id,
        full_name="Emergency Pat",
        phone="+1-555-3333",
        medical_record_number="MRN-QA-3",
    )

    receptionist_b = User(
        id="user-rec-b",
        clinic_id=clinic_b.id,
        email="receptionist@clinicb.com",
        full_name="Rec B User",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.RECEPTIONIST,
        is_active=True,
    )

    db_session.add_all(
        [receptionist_a, doctor_a, patient_1, patient_2, patient_3, receptionist_b]
    )
    db_session.commit()

    token_a = create_access_token(
        {"sub": receptionist_a.id, "clinic_id": clinic_a.id, "role": receptionist_a.role}
    )
    token_b = create_access_token(
        {"sub": receptionist_b.id, "clinic_id": clinic_b.id, "role": receptionist_b.role}
    )

    return {
        "clinic_a": clinic_a,
        "doctor_a": doctor_a,
        "patient_1": patient_1,
        "patient_2": patient_2,
        "patient_3": patient_3,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
    }


def test_issue_walkin_token_and_view_queue(client: TestClient, queue_test_setup):
    """Test issuing walk-in token and retrieving active doctor queue."""
    headers = queue_test_setup["headers_a"]
    doc_id = queue_test_setup["doctor_a"].id
    pat_id = queue_test_setup["patient_1"].id

    resp = client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": pat_id, "is_emergency": False},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["token_number"] == 1
    assert data["status"] == QueueStatus.WAITING.value
    assert data["access_code"].startswith("tk_")
    token_id = data["id"]

    # View queue
    queue_resp = client.get(f"/api/v1/queue/doctors/{doc_id}", headers=headers)
    assert queue_resp.status_code == 200
    queue = queue_resp.json()
    assert len(queue) == 1
    assert queue[0]["token_id"] == token_id
    assert queue[0]["token_number"] == 1
    assert queue[0]["patient_name"] == "John Doe"
    assert queue[0]["position"] == 1


def test_call_next_and_state_transitions(client: TestClient, queue_test_setup):
    """Test full lifecycle transitions: WAITING -> CALLED -> IN_CONSULTATION -> COMPLETED."""
    headers = queue_test_setup["headers_a"]
    doc_id = queue_test_setup["doctor_a"].id
    pat_id = queue_test_setup["patient_1"].id

    # 1. Issue token
    issue_resp = client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": pat_id, "is_emergency": False},
    )
    token_id = issue_resp.json()["id"]

    # 2. Call next
    call_resp = client.post(f"/api/v1/queue/doctors/{doc_id}/call-next", headers=headers)
    assert call_resp.status_code == 200
    called_data = call_resp.json()
    assert called_data["id"] == token_id
    assert called_data["status"] == QueueStatus.CALLED.value
    assert called_data["called_at"] is not None

    # 3. Transition to IN_CONSULTATION
    in_consult_resp = client.patch(
        f"/api/v1/queue/tokens/{token_id}/status",
        headers=headers,
        json={"status": QueueStatus.IN_CONSULTATION.value},
    )
    assert in_consult_resp.status_code == 200
    assert in_consult_resp.json()["status"] == QueueStatus.IN_CONSULTATION.value
    assert in_consult_resp.json()["consultation_start_at"] is not None

    # 4. Transition to COMPLETED
    complete_resp = client.patch(
        f"/api/v1/queue/tokens/{token_id}/status",
        headers=headers,
        json={"status": QueueStatus.COMPLETED.value},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == QueueStatus.COMPLETED.value
    assert complete_resp.json()["consultation_end_at"] is not None

    # 5. Completed token no longer appears in active queue
    queue_resp = client.get(f"/api/v1/queue/doctors/{doc_id}", headers=headers)
    assert queue_resp.status_code == 200
    assert len(queue_resp.json()) == 0


def test_illegal_state_transition_returns_422(client: TestClient, queue_test_setup):
    """Test that illegal state machine jumps return 422 Unprocessable Entity."""
    headers = queue_test_setup["headers_a"]
    doc_id = queue_test_setup["doctor_a"].id
    pat_id = queue_test_setup["patient_1"].id

    # Issue token (starts in WAITING)
    issue_resp = client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": pat_id, "is_emergency": False},
    )
    token_id = issue_resp.json()["id"]

    # Attempt illegal jump: WAITING -> COMPLETED directly
    bad_resp = client.patch(
        f"/api/v1/queue/tokens/{token_id}/status",
        headers=headers,
        json={"status": QueueStatus.COMPLETED.value},
    )
    assert bad_resp.status_code == 422
    assert "Illegal state transition" in bad_resp.json()["detail"]


def test_emergency_priority_moves_to_front(client: TestClient, queue_test_setup):
    """Verify that an emergency walk-in jumps to the front of WAITING patients."""
    headers = queue_test_setup["headers_a"]
    doc_id = queue_test_setup["doctor_a"].id
    pat1_id = queue_test_setup["patient_1"].id
    pat2_id = queue_test_setup["patient_2"].id
    em_pat_id = queue_test_setup["patient_3"].id

    # Patient 1 walk-in arrives
    client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": pat1_id, "is_emergency": False},
    )

    # Patient 2 walk-in arrives
    client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": pat2_id, "is_emergency": False},
    )

    # Emergency patient arrives
    em_resp = client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": em_pat_id, "is_emergency": True},
    )
    em_token_id = em_resp.json()["id"]

    # View queue: emergency patient must be at position 1!
    queue_resp = client.get(f"/api/v1/queue/doctors/{doc_id}", headers=headers)
    assert queue_resp.status_code == 200
    queue = queue_resp.json()
    assert len(queue) == 3
    assert queue[0]["token_id"] == em_token_id
    assert queue[0]["is_emergency"] is True
    assert queue[0]["position"] == 1

    # Call next must call the emergency patient first
    call_resp = client.post(f"/api/v1/queue/doctors/{doc_id}/call-next", headers=headers)
    assert call_resp.status_code == 200
    assert call_resp.json()["id"] == em_token_id


def test_no_show_timeout_flow(client: TestClient, queue_test_setup):
    """Test marking a called token as NO_SHOW upon timeout."""
    headers = queue_test_setup["headers_a"]
    doc_id = queue_test_setup["doctor_a"].id
    pat_id = queue_test_setup["patient_1"].id

    issue_resp = client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": pat_id, "is_emergency": False},
    )
    token_id = issue_resp.json()["id"]

    # Call patient
    client.post(f"/api/v1/queue/doctors/{doc_id}/call-next", headers=headers)

    # Patient does not show up: mark as no-show
    no_show_resp = client.post(f"/api/v1/queue/tokens/{token_id}/no-show", headers=headers)
    assert no_show_resp.status_code == 200
    assert no_show_resp.json()["status"] == QueueStatus.NO_SHOW.value

    # Queue should now be empty
    queue_resp = client.get(f"/api/v1/queue/doctors/{doc_id}", headers=headers)
    assert len(queue_resp.json()) == 0


def test_live_queue_rebuild_endpoint(client: TestClient, queue_test_setup):
    """Test calling the live queue rebuild endpoint."""
    headers = queue_test_setup["headers_a"]
    doc_id = queue_test_setup["doctor_a"].id
    pat_id = queue_test_setup["patient_1"].id

    # Issue a token
    client.post(
        "/api/v1/queue/tokens",
        headers=headers,
        json={"doctor_id": doc_id, "patient_id": pat_id, "is_emergency": False},
    )

    # Rebuild queue endpoint
    reb_resp = client.post(f"/api/v1/queue/doctors/{doc_id}/rebuild", headers=headers)
    assert reb_resp.status_code == 200
    assert reb_resp.json()["status"] == "rebuilt"
    assert reb_resp.json()["active_tokens_recovered"] == 1


def test_cross_tenant_queue_isolation(client: TestClient, queue_test_setup):
    """Verify clinic B cannot view or manipulate clinic A's queue tokens."""
    headers_b = queue_test_setup["headers_b"]
    headers_a = queue_test_setup["headers_a"]
    doc_id = queue_test_setup["doctor_a"].id
    pat_id = queue_test_setup["patient_1"].id

    # Issue token in Clinic A
    issue_resp = client.post(
        "/api/v1/queue/tokens",
        headers=headers_a,
        json={"doctor_id": doc_id, "patient_id": pat_id, "is_emergency": False},
    )
    token_id = issue_resp.json()["id"]

    # Clinic B attempts to issue token for Clinic A's doctor -> 404
    cross_issue = client.post(
        "/api/v1/queue/tokens",
        headers=headers_b,
        json={"doctor_id": doc_id, "patient_id": pat_id, "is_emergency": False},
    )
    assert cross_issue.status_code == 404

    # Clinic B attempts to update status of Clinic A's token -> 404
    cross_update = client.patch(
        f"/api/v1/queue/tokens/{token_id}/status",
        headers=headers_b,
        json={"status": QueueStatus.CALLED.value},
    )
    assert cross_update.status_code == 404
