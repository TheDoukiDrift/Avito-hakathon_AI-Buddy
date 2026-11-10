"""Test bootstrap: SQLite file DB, seeded per test, ASGI client without a server."""

from __future__ import annotations

import os
import pathlib
import tempfile

TEST_DB = pathlib.Path(tempfile.gettempdir()) / "ai_buddy_pytest.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_API_KEY"] = ""

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seeds import seed  # noqa: E402

INTERN = "intern@example.com"
MENTOR = "mentor@example.com"
MANAGER = "manager@example.com"
HR_BP = "hr.bp@example.com"
PASSWORD = "test1234"


@pytest_asyncio.fixture(autouse=True)
async def database():
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with get_session_factory()() as session:
        await seed(session)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


async def auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    payload = await login(client, email)
    return {"Authorization": f"Bearer {payload['token']}"}


async def user_id(client: AsyncClient, email: str) -> int:
    headers = await auth_headers(client, email)
    response = await client.get("/api/me", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["id"]
