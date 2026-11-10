from __future__ import annotations

from tests.conftest import HR_BP, INTERN, MANAGER, MENTOR, auth_headers


async def _create(client, headers, **overrides) -> dict:
    payload = {
        "type": "day_off",
        "date_from": "2026-11-20",
        "date_to": "2026-11-20",
        "reason": "Личные дела",
    }
    payload.update(overrides)
    response = await client.post("/api/absences", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_draft_confirm_approve_lifecycle(client):
    intern_headers = await auth_headers(client, INTERN)
    manager_headers = await auth_headers(client, MANAGER)

    draft = await _create(client, intern_headers)
    assert draft["status"] == "draft"
    assert draft["decided_by"] is None

    confirmed = await client.post(f"/api/absences/{draft['id']}/confirm", headers=intern_headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "pending_approval"

    approved = await client.post(
        f"/api/absences/{draft['id']}/approve",
        headers=manager_headers,
        json={"comment": "Согласовано"},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved"
    assert body["decided_by"] is not None
    assert body["decided_at"] is not None


async def test_reject_flow(client):
    intern_headers = await auth_headers(client, INTERN)
    hr_headers = await auth_headers(client, HR_BP)
    draft = await _create(client, intern_headers)
    await client.post(f"/api/absences/{draft['id']}/confirm", headers=intern_headers)

    rejected = await client.post(f"/api/absences/{draft['id']}/reject", headers=hr_headers)
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


async def test_cannot_confirm_someone_elses_draft(client):
    intern_headers = await auth_headers(client, INTERN)
    mentor_headers = await auth_headers(client, MENTOR)
    draft = await _create(client, intern_headers)

    response = await client.post(f"/api/absences/{draft['id']}/confirm", headers=mentor_headers)
    assert response.status_code == 403


async def test_cannot_confirm_twice(client):
    headers = await auth_headers(client, INTERN)
    draft = await _create(client, headers)
    first = await client.post(f"/api/absences/{draft['id']}/confirm", headers=headers)
    assert first.status_code == 200
    again = await client.post(f"/api/absences/{draft['id']}/confirm", headers=headers)
    assert again.status_code == 422
    assert "черновик" in again.json()["detail"].lower()


async def test_cannot_approve_unconfirmed_draft(client):
    intern_headers = await auth_headers(client, INTERN)
    manager_headers = await auth_headers(client, MANAGER)
    draft = await _create(client, intern_headers)

    response = await client.post(f"/api/absences/{draft['id']}/approve", headers=manager_headers)
    assert response.status_code == 422


async def test_date_range_is_validated(client):
    headers = await auth_headers(client, INTERN)
    response = await client.post(
        "/api/absences",
        headers=headers,
        json={"type": "vacation", "date_from": "2026-11-20", "date_to": "2026-11-10"},
    )
    assert response.status_code == 422


async def test_invalid_type_is_rejected(client):
    headers = await auth_headers(client, INTERN)
    response = await client.post(
        "/api/absences",
        headers=headers,
        json={"type": "sabbatical", "date_from": "2026-11-20", "date_to": "2026-11-20"},
    )
    assert response.status_code == 422


async def test_list_shows_own_requests_only(client):
    intern_headers = await auth_headers(client, INTERN)
    draft = await _create(client, intern_headers)
    response = await client.get("/api/absences", headers=intern_headers)
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [draft["id"]]


async def test_absence_requires_auth(client):
    assert (await client.get("/api/absences")).status_code == 401
    assert (await client.post("/api/absences", json={})).status_code == 401
