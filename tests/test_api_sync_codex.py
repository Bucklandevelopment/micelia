"""
Tests for the Sync API router (app/api/v1/sync.py).

The three endpoints read the sync service from ``request.app.state.md_sync``
(the ``app.state`` pattern, like ``dashboard.py``/``agents.py``, unlike
``budget.py``/``tunnel.py`` which import ``get_*`` at module level). So we inject
a fake straight into ``app.state`` — nothing is monkeypatched. When ``md_sync`` is
absent, ``getattr(..., None)`` yields ``None`` and each endpoint takes its
"not initialized" branch.

Mock shape: ``get_status`` is synchronous → plain ``MagicMock`` return; ``full_sync``
and ``get_today_inbox_md`` are ``await``ed by the router → ``AsyncMock``.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import sync
from app.core.security import api_key_manager

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-sync", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app(md_sync=None) -> FastAPI:
    """Build a FastAPI app with only the sync router; optionally seed app.state."""
    app = FastAPI()
    app.include_router(sync.router, prefix="/api/v1")
    if md_sync is not None:
        app.state.md_sync = md_sync
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------- fakes


def fake_md_sync(*, status=None, full_sync_result=None, inbox=None) -> MagicMock:
    """MarkdownSyncService double: sync get_status, async full_sync/get_today_inbox_md."""
    svc = MagicMock()
    svc.get_status.return_value = status if status is not None else {
        "status": "enabled",
        "last_run": "2026-07-12T00:00:00+00:00",
    }
    svc.full_sync = AsyncMock(return_value=full_sync_result)
    svc.get_today_inbox_md = AsyncMock(return_value=inbox)
    return svc


# ---------------------------------------------------------------- /status


async def test_status_disabled_when_no_service():
    # No md_sync in state → getattr None → "disabled" branch.
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/sync/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "disabled"
    assert "not initialized" in body["message"]


async def test_status_delegates_to_get_status():
    svc = fake_md_sync(status={"status": "enabled", "last_run": "2026-07-12T10:00:00Z"})
    async with client_for(build_app(md_sync=svc)) as ac:
        resp = await ac.get("/api/v1/sync/status", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"status": "enabled", "last_run": "2026-07-12T10:00:00Z"}
    svc.get_status.assert_called_once_with()


# ---------------------------------------------------------------- /run


async def test_run_error_when_no_service():
    # No md_sync → "error" branch, full_sync never awaited.
    svc = fake_md_sync()  # standalone fake to assert it is *not* used
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/sync/run", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "error"
    assert "not initialized" in body["message"]
    svc.full_sync.assert_not_awaited()


async def test_run_triggers_full_sync():
    result = {"synced": 3, "conflicts": 0}
    svc = fake_md_sync(full_sync_result=result)
    async with client_for(build_app(md_sync=svc)) as ac:
        resp = await ac.post("/api/v1/sync/run", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["result"] == result
    assert "timestamp" in body
    svc.full_sync.assert_awaited_once_with()


# ---------------------------------------------------------------- /inbox


async def test_inbox_503_when_no_service():
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/sync/inbox", headers=AUTH)
    assert resp.status_code == 503
    assert "not initialized" in resp.text


async def test_inbox_returns_content():
    md = "# Inbox 2026-07-12\n\n- prompt one\n- prompt two\n"
    svc = fake_md_sync(inbox=md)
    async with client_for(build_app(md_sync=svc)) as ac:
        resp = await ac.get("/api/v1/sync/inbox", headers=AUTH)
    assert resp.status_code == 200
    assert resp.text == md
    assert resp.headers["content-type"].startswith("text/markdown")
    svc.get_today_inbox_md.assert_awaited_once_with()


@pytest.mark.parametrize("empty", ["", None])
async def test_inbox_fallback_when_empty(empty):
    # Empty/None content → default "no captured prompts" markdown.
    svc = fake_md_sync(inbox=empty)
    async with client_for(build_app(md_sync=svc)) as ac:
        resp = await ac.get("/api/v1/sync/inbox", headers=AUTH)
    assert resp.status_code == 200
    assert "# Inbox " in resp.text
    assert "_No captured prompts today._" in resp.text


# ---------------------------------------------------------------- auth


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/sync/status"),
        ("post", "/api/v1/sync/run"),
        ("get", "/api/v1/sync/inbox"),
    ],
)
async def test_requires_auth(method, path):
    # No API key on any endpoint → verify_auth rejects before the body runs.
    async with client_for(build_app()) as ac:
        resp = await getattr(ac, method)(path)
    assert resp.status_code in (401, 403)
