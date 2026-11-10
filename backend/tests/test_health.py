from __future__ import annotations


async def test_health(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_root_metadata(client):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["health"] == "/api/health"


async def test_openapi_is_served(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    for path in ("/api/health", "/api/auth/login", "/api/chat/stream", "/api/checklist"):
        assert path in paths
