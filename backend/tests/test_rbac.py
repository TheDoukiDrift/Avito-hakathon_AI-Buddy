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
    mentor_headers = await auth_headers(client, MENTOR)
    checklist = (await client.get("/api/checklist", headers=intern_headers)).json()
    item_id = checklist["items"][0]["id"]

    response = await client.post(f"/api/checklist/{item_id}/complete", headers=mentor_headers)
    # the mentor marks *their own* (empty) checklist, not the intern's
    assert response.status_code == 200
    intern_after = (await client.get("/api/checklist", headers=intern_headers)).json()
    assert intern_after["done"] == 0


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
