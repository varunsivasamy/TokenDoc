from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_200_and_ok():
    """Verify that GET /health returns 200 with status ok and app metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "ClinicQ"
    assert "version" in data
