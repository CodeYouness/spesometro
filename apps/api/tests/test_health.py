from fastapi.testclient import TestClient
from spesometro_api.main import app


def test_health_risponde_200_json() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"status": "ok"}
