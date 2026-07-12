"""
Tests for the Audit API router (app/api/v1/audit.py).

The four endpoints obtain the session service through a **module-level** import
(``from app.services.entire_session import get_entire_service``), like ``budget.py``
and ``tunnel.py`` and unlike ``agents.py``/``dashboard.py`` which read collaborators
from ``app.state``. So we monkeypatch the name already bound in the ``audit`` module
namespace (``app.api.v1.audit.get_entire_service``) to return a fake — the real
singleton (``EntireSessionService``) is never constructed.

Mock shape: every method the router touches (``get_status``, ``get_sessions``,
``get_session``, ``get_sessions_for_prompt``) is **synchronous** — the router does
not ``await`` any of them — so the fake is a plain ``MagicMock`` with flat returns.
"""

import contextlib
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import audit
from app.core.security import api_key_manager

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-audit", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app() -> FastAPI:
    """Build a FastAPI app with only the audit router mounted."""
    app = FastAPI()
    app.include_router(audit.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------- fakes


def fake_service(**overrides) -> MagicMock:
    """EntireSessionService double; every method the router uses is synchronous."""
    svc = MagicMock()
    svc.get_status.return_value = {"available": True, "sessions_tracked": 2}
    svc.get_sessions.return_value = [{"id": "s1"}, {"id": "s2"}]
    svc.get_session.return_value = {"id": "s1", "prompt_id": "p1"}
    svc.get_sessions_for_prompt.return_value = [{"id": "s1"}]
    for key, value in overrides.items():
        getattr(svc, key).return_value = value
    return svc


@pytest.fixture
def patch_service(monkeypatch):
    """Install a given fake as ``get_entire_service`` in the audit module."""

    def _install(svc: MagicMock) -> MagicMock:
        monkeypatch.setattr("app.api.v1.audit.get_entire_service", lambda: svc)
        return svc

    return _install


# ---------------------------------------------------------------- /status


async def test_status_delegates_to_get_status(patch_service):
    svc = patch_service(fake_service())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/audit/status", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"available": True, "sessions_tracked": 2}
    svc.get_status.assert_called_once_with()


# ---------------------------------------------------------------- /sessions


async def test_list_sessions_defaults(patch_service):
    svc = patch_service(fake_service())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/audit/sessions", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["sessions"] == [{"id": "s1"}, {"id": "s2"}]
    assert body["total"] == 2
    svc.get_sessions.assert_called_once_with(limit=50, offset=0)


async def test_list_sessions_echoes_limit_offset(patch_service):
    svc = patch_service(fake_service(get_sessions=[{"id": "s3"}]))
    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/audit/sessions", params={"limit": 10, "offset": 5}, headers=AUTH
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sessions"] == [{"id": "s3"}]
    assert body["total"] == 1
    svc.get_sessions.assert_called_once_with(limit=10, offset=5)


# ---------------------------------------------------------------- /sessions/{id}


async def test_get_session_found(patch_service):
    svc = patch_service(fake_service())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/audit/sessions/s1", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"id": "s1", "prompt_id": "p1"}
    svc.get_session.assert_called_once_with("s1")


async def test_get_session_not_found_404(patch_service):
    patch_service(fake_service(get_session=None))
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/audit/sessions/missing", headers=AUTH)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Session not found"


# ---------------------------------------------------------------- /prompts/{id}/sessions


async def test_get_prompt_sessions(patch_service):
    svc = patch_service(fake_service())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/audit/prompts/p1/sessions", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"prompt_id": "p1", "sessions": [{"id": "s1"}]}
    svc.get_sessions_for_prompt.assert_called_once_with("p1")


# ---------------------------------------------------------------- auth


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/audit/status",
        "/api/v1/audit/sessions",
        "/api/v1/audit/sessions/s1",
        "/api/v1/audit/prompts/p1/sessions",
    ],
)
async def test_requires_auth(path):
    # No API key on any endpoint → verify_auth rejects before the body runs.
    async with client_for(build_app()) as ac:
        resp = await ac.get(path)
    assert resp.status_code in (401, 403)
