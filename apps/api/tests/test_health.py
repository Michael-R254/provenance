from fastapi.testclient import TestClient

from provenance.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cors_rejects_unknown_origin() -> None:
    client = TestClient(create_app())
    response = client.get("/health", headers={"Origin": "https://example.invalid"})
    assert "access-control-allow-origin" not in response.headers
