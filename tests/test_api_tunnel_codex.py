"""
Tests for the Tunnel API router (app/api/v1/tunnel.py).

The four endpoints obtain the tunnel service through a **module-level** import
(``from app.services.tunnel import get_tunnel_service``), like ``budget.py`` and
unlike ``agents.py``/``dashboard.py`` which read collaborators from ``app.state``.
So we monkeypatch the name already bound in the ``tunnel`` module namespace
(``app.api.v1.tunnel.get_tunnel_service``) to yield a fake service — the real
singleton (``TunnelService``) is never constructed, so pyngrok is never imported
and no network is touched.

Mock shape: ``start``/``stop`` are ``await``ed by the router → ``AsyncMock``;
``get_info`` is synchronous → ``MagicMock`` returning a flat dict; ``is_connected``
and ``public_url`` are attributes → plain values on the ``MagicMock``.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import tunnel
from app.core.security import api_key_manager

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-tunnel", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app() -> FastAPI:
    """Build a FastAPI app with only the tunnel router mounted."""
    app = FastAPI()
    app.include_router(tunnel.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------- fakes


def fake_service(*, connected: bool = False, url=None, start_returns=None) -> MagicMock:
    """TunnelService double: async start/stop, sync get_info, attribute flags."""
    svc = MagicMock()
    svc.is_connected = connected
    svc.public_url = url
    svc.start = AsyncMock(return_value=start_returns)
    svc.stop = AsyncMock(return_value=None)
    svc.get_info.return_value = {
        "connected": connected,
        "public_url": url,
        "started_at": "2026-07-12T00:00:00+00:00" if connected else None,
    }
    return svc


@pytest.fixture
def patch_service(monkeypatch):
    """Return a helper that installs a given fake as ``get_tunnel_service``."""

    def _install(svc: MagicMock) -> MagicMock:
        monkeypatch.setattr("app.api.v1.tunnel.get_tunnel_service", lambda: svc)
        return svc

    return _install


# ---------------------------------------------------------------- /status


async def test_status_returns_get_info(patch_service):
    svc = patch_service(fake_service(connected=True, url="https://abc.ngrok.io"))
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/tunnel/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["public_url"] == "https://abc.ngrok.io"
    svc.get_info.assert_called_once_with()
    svc.start.assert_not_awaited()


# ---------------------------------------------------------------- /info


async def test_info_returns_get_info(patch_service):
    svc = patch_service(fake_service(connected=False))
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/tunnel/info", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"connected": False, "public_url": None, "started_at": None}
    svc.get_info.assert_called_once_with()


# ---------------------------------------------------------------- /start


async def test_start_when_already_connected(patch_service):
    # Branch A: is_connected truthy → early return, start() never awaited.
    svc = patch_service(fake_service(connected=True, url="https://live.ngrok.io"))
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/tunnel/start", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {
        "success": True,
        "message": "Tunnel already running",
        "public_url": "https://live.ngrok.io",
    }
    svc.start.assert_not_awaited()


async def test_start_success_with_body_port(patch_service):
    # Branch B: not connected + start() returns a URL. Body port is forwarded.
    svc = patch_service(
        fake_service(connected=False, start_returns="https://new.ngrok.io")
    )
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/tunnel/start", json={"port": 9001}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "public_url": "https://new.ngrok.io"}
    svc.start.assert_awaited_once_with(9001)


async def test_start_success_no_body_passes_none_port(patch_service):
    # No body → request is None → start() is awaited with port=None.
    svc = patch_service(
        fake_service(connected=False, start_returns="https://new.ngrok.io")
    )
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/tunnel/start", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["public_url"] == "https://new.ngrok.io"
    svc.start.assert_awaited_once_with(None)


async def test_start_empty_body_passes_none_port(patch_service):
    # Empty JSON object → request.port defaults to None.
    svc = patch_service(
        fake_service(connected=False, start_returns="https://new.ngrok.io")
    )
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/tunnel/start", json={}, headers=AUTH)
    assert resp.status_code == 200
    svc.start.assert_awaited_once_with(None)


async def test_start_failure_raises_500(patch_service):
    # Branch C: not connected + start() returns None → HTTP 500.
    svc = patch_service(fake_service(connected=False, start_returns=None))
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/tunnel/start", headers=AUTH)
    assert resp.status_code == 500
    assert "Failed to start tunnel" in resp.json()["detail"]
    svc.start.assert_awaited_once_with(None)


# ---------------------------------------------------------------- /stop


async def test_stop_when_not_connected(patch_service):
    # Branch A: not connected → early return, stop() never awaited.
    svc = patch_service(fake_service(connected=False))
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/tunnel/stop", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "No tunnel running"}
    svc.stop.assert_not_awaited()


async def test_stop_when_connected(patch_service):
    # Branch B: connected → stop() awaited, then success message.
    svc = patch_service(fake_service(connected=True, url="https://live.ngrok.io"))
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/tunnel/stop", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Tunnel stopped"}
    svc.stop.assert_awaited_once_with()


# ---------------------------------------------------------------- auth


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/tunnel/status"),
        ("get", "/api/v1/tunnel/info"),
        ("post", "/api/v1/tunnel/start"),
        ("post", "/api/v1/tunnel/stop"),
    ],
)
async def test_requires_auth(method, path):
    # No API key on any endpoint → verify_auth rejects before the body runs.
    async with client_for(build_app()) as ac:
        resp = await getattr(ac, method)(path)
    assert resp.status_code in (401, 403)
