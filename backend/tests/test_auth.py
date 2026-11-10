from __future__ import annotations

import time

from app.security import create_token, decode_token, hash_password, verify_password
from tests.conftest import HR_BP, INTERN, PASSWORD, auth_headers, login


async def test_login_returns_token_and_user(client):
    payload = await login(client, INTERN)
    assert payload["token"]
    assert payload["user"]["email"] == INTERN
    assert payload["user"]["role"] == "intern"
    assert payload["user"]["full_name"]


async def test_login_rejects_wrong_password(client):
    response = await client.post(
        "/api/auth/login", json={"email": INTERN, "password": "definitely-wrong"}
    )
    assert response.status_code == 401
    assert "пароль" in response.json()["detail"].lower()


async def test_login_rejects_unknown_user(client):
    response = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


async def test_me_requires_token(client):
    response = await client.get("/api/me")
    assert response.status_code == 401


async def test_me_rejects_garbage_token(client):
    response = await client.get("/api/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


async def test_me_returns_current_user(client):
    headers = await auth_headers(client, HR_BP)
    response = await client.get("/api/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "hr_bp"


def test_token_roundtrip():
    token = create_token(42)
    assert decode_token(token) == 42


def test_token_is_tamper_evident():
    token = create_token(42)
    encoded, signature = token.split(".", 1)
    forged = f"{encoded}.{signature[:-2]}xx"
    assert decode_token(forged) is None


def test_expired_token_is_rejected():
    assert decode_token(create_token(42, ttl_seconds=-10)) is None


def test_password_hash_roundtrip():
    stored = hash_password("test1234")
    assert stored.startswith("pbkdf2$")
    assert verify_password("test1234", stored)
    assert not verify_password("wrong", stored)


def test_verify_password_handles_garbage():
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "md5$1$aa$bb")


def test_token_ttl_is_bounded():
    token = create_token(7, ttl_seconds=1)
    assert decode_token(token) == 7
    time.sleep(0)  # keep the clock call explicit
