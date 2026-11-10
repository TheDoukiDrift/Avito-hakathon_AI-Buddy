from __future__ import annotations

from tests.conftest import INTERN, auth_headers


async def test_contacts_returns_team_members(client):
    headers = await auth_headers(client, INTERN)
    response = await client.get("/api/contacts", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert {contact["role"] for contact in body} == {"наставник", "руководитель", "HR BP"}
    assert all(contact["email"].endswith("@example.com") for contact in body)


async def test_contacts_query_filter(client):
    headers = await auth_headers(client, INTERN)
    response = await client.get("/api/contacts?query=hr", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["email"] == "hr.bp@example.com"


async def test_contacts_query_without_matches(client):
    headers = await auth_headers(client, INTERN)
    response = await client.get("/api/contacts?query=devops", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_contacts_require_auth(client):
    assert (await client.get("/api/contacts")).status_code == 401
