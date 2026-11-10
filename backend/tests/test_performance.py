"""ADR-03: every local read stays under one second — measured, not assumed."""

from __future__ import annotations

import time

from tests.conftest import INTERN, auth_headers

BUDGET_SECONDS = 1.0

READ_PATHS = (
    "/api/checklist",
    "/api/contacts",
    "/api/absences",
    "/api/audit",
    "/api/chat/history",
)


async def test_local_reads_stay_under_one_second(client):
    headers = await auth_headers(client, INTERN)
    for path in READ_PATHS:
        started = time.perf_counter()
        response = await client.get(path, headers=headers)
        elapsed = time.perf_counter() - started
        assert response.status_code == 200, path
        assert elapsed < BUDGET_SECONDS, f"{path} took {elapsed:.3f}s"
