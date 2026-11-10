from __future__ import annotations

from tests.conftest import HR_BP, INTERN, MANAGER, MENTOR, auth_headers, user_id


async def _intern_absence(client, headers) -> dict:
    response = await client.post(
        "/api/absences",
        headers=headers,
        json={
            "type": "day_off",
            "date_from": "2026-11-12",
            "date_to": "2026-11-12",
            "reason": "Личные дела",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_intern_cannot_read_another_users_checklist(client):
    intern_headers = await auth_headers(client, INTERN)
    mentor_id = await user_id(client, MENTOR)

    response = await client.get(f"/api/checklist?user_id={mentor_id}", headers=intern_headers)
    assert response.status_code == 403
    assert "роли" in response.json()["detail"].lower()


async def test_intern_cannot_see_team_absences(client):
    intern_headers = await auth_headers(client, INTERN)
    mentor_headers = await auth_headers(client, MENTOR)

    # the mentor files their own request; the intern must not see it
    mentor_request = await client.post(
        "/api/absences",
        headers=mentor_headers,
        json={"type": "vacation", "date_from": "2026-12-01", "date_to": "2026-12-05"},
    )
    assert mentor_request.status_code == 201

    response = await client.get("/api/absences", headers=intern_headers)
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert mentor_request.json()["id"] not in ids


async def test_intern_cannot_approve_others_absence(client):
    intern_headers = await auth_headers(client, INTERN)
    mentor_headers = await auth_headers(client, MENTOR)

    mentor_request = await client.post(
        "/api/absences",
        headers=mentor_headers,
        json={"type": "day_off", "date_from": "2026-12-10", "date_to": "2026-12-10"},
    )
    request_id = mentor_request.json()["id"]
    await client.post(f"/api/absences/{request_id}/confirm", headers=mentor_headers)

    response = await client.post(f"/api/absences/{request_id}/approve", headers=intern_headers)
    assert response.status_code == 403


async def test_intern_cannot_approve_own_absence(client):
    intern_headers = await auth_headers(client, INTERN)
    request = await _intern_absence(client, intern_headers)
    await client.post(f"/api/absences/{request['id']}/confirm", headers=intern_headers)

    response = await client.post(f"/api/absences/{request['id']}/approve", headers=intern_headers)
    assert response.status_code == 403


async def test_mentor_sees_intern_checklist(client):
    mentor_headers = await auth_headers(client, MENTOR)
    response = await client.get("/api/checklist", headers=mentor_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] > 0
    assert body["full_name"]


async def test_mentor_cannot_complete_intern_checklist_item(client):
    intern_headers = await auth_headers(client, INTERN)
    checklist = (await client.get("/api/checklist", headers=intern_headers)).json()
    item_id = checklist["items"][0]["id"]

    # The matrix grants completion to the intern only: privileged roles get read-only
    # visibility of their wards, so marking an item is a 403 (not a silent own-list mark).
    for email in (MENTOR, MANAGER, HR_BP):
        headers = await auth_headers(client, email)
        response = await client.post(f"/api/checklist/{item_id}/complete", headers=headers)
        assert response.status_code == 403, email

    intern_after = (await client.get("/api/checklist", headers=intern_headers)).json()
    assert intern_after["done"] == 0


async def test_intern_completes_own_checklist_item(client):
    intern_headers = await auth_headers(client, INTERN)
    checklist = (await client.get("/api/checklist", headers=intern_headers)).json()
    item_id = checklist["items"][0]["id"]

    response = await client.post(f"/api/checklist/{item_id}/complete", headers=intern_headers)
    assert response.status_code == 200
    body = response.json()
    # the endpoint returns the full item, not just the new status
    assert body["id"] == item_id
    assert body["status"] == "done"
    assert body["title"]

    intern_after = (await client.get("/api/checklist", headers=intern_headers)).json()
    assert intern_after["done"] == 1


async def test_hr_bp_lists_team_absences(client):
    intern_headers = await auth_headers(client, INTERN)
    hr_headers = await auth_headers(client, HR_BP)

    request = await _intern_absence(client, intern_headers)
    await client.post(f"/api/absences/{request['id']}/confirm", headers=intern_headers)

    response = await client.get("/api/absences", headers=hr_headers)
    assert response.status_code == 200
    assert request["id"] in {item["id"] for item in response.json()}


async def test_manager_lists_team_absences(client):
    intern_headers = await auth_headers(client, INTERN)
    manager_headers = await auth_headers(client, MANAGER)
    request = await _intern_absence(client, intern_headers)

    response = await client.get("/api/absences", headers=manager_headers)
    assert response.status_code == 200
    assert request["id"] in {item["id"] for item in response.json()}


async def test_mentor_reads_same_team_absence_and_unknown_id_is_404(client):
    intern_headers = await auth_headers(client, INTERN)
    mentor_headers = await auth_headers(client, MENTOR)
    request = await _intern_absence(client, intern_headers)

    response = await client.get(f"/api/absences/{request['id']}", headers=mentor_headers)
    assert response.status_code == 200  # same team → allowed

    # HR BP always allowed; a random unknown id is a 404
    hr_headers = await auth_headers(client, HR_BP)
    missing = await client.get("/api/absences/9999", headers=hr_headers)
    assert missing.status_code == 404


async def test_audit_feed_is_scoped_by_role(client):
    from app.db import get_session_factory
    from app.models import Role, User
    from app.services import audit as audit_service

    intern_headers = await auth_headers(client, INTERN)
    mentor_headers = await auth_headers(client, MENTOR)
    hr_headers = await auth_headers(client, HR_BP)

    checklist = (await client.get("/api/checklist", headers=intern_headers)).json()
    item_id = checklist["items"][0]["id"]
    await client.post(f"/api/checklist/{item_id}/complete", headers=intern_headers)

    # An event from another team: visible only to HR BP.
    async with get_session_factory()() as session:
        outsider = User(
            email="outsider@example.com",
            password_hash="x",
            role=Role.intern,
            full_name="Чужой",
            team="Other",
        )
        session.add(outsider)
        await session.flush()
        await audit_service.log(session, outsider.id, "test.other_team")
        await session.commit()

    own = {
        event["action"] for event in (await client.get("/api/audit", headers=intern_headers)).json()
    }
    assert "checklist.completed" in own
    assert "test.other_team" not in own

    team = {
        event["action"] for event in (await client.get("/api/audit", headers=mentor_headers)).json()
    }
    assert "checklist.completed" in team
    assert "test.other_team" not in team

    everything = {
        event["action"] for event in (await client.get("/api/audit", headers=hr_headers)).json()
    }
    assert "test.other_team" in everything


async def test_audit_requires_auth(client):
    assert (await client.get("/api/audit")).status_code == 401
