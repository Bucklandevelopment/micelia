"""
Endpoint tests for the register → login → micelia funnel router (app.api.v1.auth).

The shared `test_app` fixture in conftest.py deliberately does NOT mount the auth
router and never sets `app.state.user_store`, so the funnel endpoints
(register / login / refresh / me / setup) had zero endpoint-level coverage. This
file is self-contained: it builds a minimal FastAPI app mounting ONLY the auth
router, injects a fake `user_store` (AsyncMock) into `app.state`, and drives the
endpoints with httpx.AsyncClient + ASGITransport (same harness as conftest.client).

Boundaries mocked (no infra, no network, no DB):
  - `user_store` → AsyncMock.
  - `pwd_context.hash/verify` → deterministic stub. This is REQUIRED here (not just
    for speed): the current venv ships bcrypt 5.0.0 with passlib 1.7.4, whose
    backend probe raises `ValueError: password cannot be longer than 72 bytes` on
    the first real hash/verify — i.e. register/login password hashing is broken at
    runtime. See the DECISIÓN PENDIENTE recorded in docs/ITERATION_LOG.md. Stubbing
    the crypto boundary lets these tests exercise the endpoint control flow
    (routing, status codes, store calls, JWT issuance) independently of that bug.
`jwt_auth` (jose JWT) runs for real; `audit_logger` is None-safe (event_store=None).

Covers every branch of app/api/v1/auth.py.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import auth as auth_module
from app.core.security import jwt_auth, verify_auth
from app.services.user_store import DuplicateEmailError

_PASSWORD = "supersecret"
_ADMIN_PASSWORD = "admin-password"


def _stub_hash(pw: str) -> str:
    return f"hashed::{pw}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def stub_crypto(monkeypatch):
    """Replace the bcrypt-backed pwd_context boundary with a deterministic stub."""
    monkeypatch.setattr(auth_module.pwd_context, "hash", _stub_hash)
    monkeypatch.setattr(
        auth_module.pwd_context, "verify", lambda pw, h: h == _stub_hash(pw)
    )


def _build_app(user_store) -> FastAPI:
    """Minimal app mounting only the auth router, with an injected user_store."""
    app = FastAPI()
    app.state.user_store = user_store
    app.state.event_store = None  # keeps audit_logger a no-op (None-safe)
    app.include_router(auth_module.router, prefix="/api/v1")
    return app


def _fake_store() -> AsyncMock:
    store = AsyncMock()
    store.create_user = AsyncMock()
    store.get_user_by_email = AsyncMock(return_value=None)
    store.touch_last_login = AsyncMock()
    return store


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture()
def store() -> AsyncMock:
    return _fake_store()


@pytest.fixture()
async def client_with_store(store):
    async with await _client(_build_app(store)) as ac:
        yield ac


@pytest.fixture()
async def client_no_store():
    async with await _client(_build_app(None)) as ac:
        yield ac


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_happy_path_returns_tokens(client_with_store, store):
    user_id = str(uuid4())
    store.create_user = AsyncMock(return_value={"user_id": user_id})

    resp = await client_with_store.post(
        "/api/v1/auth/register",
        json={"email": "New.User@Example.com", "password": _PASSWORD},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] > 0
    # Auto-login: the access token subject is the new user_id.
    assert jwt_auth.decode_token(body["access_token"])["sub"] == user_id

    # create_user called with normalized email + a hashed (not plaintext) password.
    store.create_user.assert_awaited_once()
    assert store.create_user.await_args is not None
    called_email, called_hash = store.create_user.await_args.args
    assert called_email == "new.user@example.com"  # strip + lower
    assert called_hash == _stub_hash(_PASSWORD)


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client_with_store, store):
    store.create_user = AsyncMock(side_effect=DuplicateEmailError("dup"))

    resp = await client_with_store.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": _PASSWORD},
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == "Email already registered"


@pytest.mark.asyncio
async def test_register_without_store_returns_503(client_no_store):
    resp = await client_no_store.post(
        "/api/v1/auth/register",
        json={"email": "nobody@example.com", "password": _PASSWORD},
    )
    assert resp.status_code == 503
    assert resp.json()["detail"] == "User registration not available"


@pytest.mark.asyncio
async def test_register_invalid_email_returns_422(client_with_store, store):
    resp = await client_with_store.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": _PASSWORD},
    )
    assert resp.status_code == 422
    store.create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_short_password_returns_422(client_with_store, store):
    resp = await client_with_store.post(
        "/api/v1/auth/register",
        json={"email": "user@example.com", "password": "short"},
    )
    assert resp.status_code == 422
    store.create_user.assert_not_awaited()


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_registered_user_happy_path(client_with_store, store):
    user_id = str(uuid4())
    store.get_user_by_email = AsyncMock(
        return_value={
            "user_id": user_id,
            "password_hash": _stub_hash(_PASSWORD),
            "is_active": True,
        }
    )

    resp = await client_with_store.post(
        "/api/v1/auth/login",
        json={"username": "user@example.com", "password": _PASSWORD},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert jwt_auth.decode_token(body["access_token"])["sub"] == user_id
    store.get_user_by_email.assert_awaited_once_with(
        "user@example.com", include_hash=True
    )
    # touch_last_login receives a UUID built from the user_id.
    store.touch_last_login.assert_awaited_once()
    assert store.touch_last_login.await_args is not None
    (touched_id,) = store.touch_last_login.await_args.args
    assert str(touched_id) == user_id


@pytest.mark.asyncio
async def test_login_disabled_account_returns_403(client_with_store, store):
    store.get_user_by_email = AsyncMock(
        return_value={
            "user_id": str(uuid4()),
            "password_hash": _stub_hash(_PASSWORD),
            "is_active": False,
        }
    )

    resp = await client_with_store.post(
        "/api/v1/auth/login",
        json={"username": "user@example.com", "password": _PASSWORD},
    )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Account disabled"
    store.touch_last_login.assert_not_awaited()


@pytest.mark.asyncio
async def test_login_admin_fallback_happy_path(client_with_store, store, monkeypatch):
    # No registered user matches → falls back to the .env single-admin login.
    store.get_user_by_email = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_module.settings, "auth_username", "admin")
    monkeypatch.setattr(
        auth_module.jwt_auth, "verify_password", lambda pw: pw == _ADMIN_PASSWORD
    )

    resp = await client_with_store.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": _ADMIN_PASSWORD},
    )

    assert resp.status_code == 200
    assert jwt_auth.decode_token(resp.json()["access_token"])["sub"] == "admin"


@pytest.mark.asyncio
async def test_login_invalid_credentials_returns_401(
    client_with_store, store, monkeypatch
):
    store.get_user_by_email = AsyncMock(return_value=None)
    monkeypatch.setattr(auth_module.settings, "auth_username", "admin")
    monkeypatch.setattr(auth_module.jwt_auth, "verify_password", lambda pw: False)

    resp = await client_with_store.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_without_store_uses_admin_fallback(client_no_store, monkeypatch):
    # user_store is None → the registered-user block is skipped entirely.
    monkeypatch.setattr(auth_module.settings, "auth_username", "admin")
    monkeypatch.setattr(
        auth_module.jwt_auth, "verify_password", lambda pw: pw == _ADMIN_PASSWORD
    )

    resp = await client_no_store.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": _ADMIN_PASSWORD},
    )

    assert resp.status_code == 200
    assert jwt_auth.decode_token(resp.json()["access_token"])["sub"] == "admin"


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_valid_token_returns_new_pair(client_with_store):
    refresh = jwt_auth.create_refresh_token(subject="user-123")

    resp = await client_with_store.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert jwt_auth.decode_token(body["access_token"])["sub"] == "user-123"
    assert jwt_auth.decode_token(body["access_token"])["type"] == "access"
    assert jwt_auth.decode_token(body["refresh_token"])["type"] == "refresh"


@pytest.mark.asyncio
async def test_refresh_wrong_token_type_returns_401(client_with_store):
    # An access token has type="access" → rejected by the refresh endpoint.
    access = jwt_auth.create_access_token(subject="user-123")

    resp = await client_with_store.post(
        "/api/v1/auth/refresh", json={"refresh_token": access}
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token type"


@pytest.mark.asyncio
async def test_refresh_garbage_token_returns_401(client_with_store):
    resp = await client_with_store.post(
        "/api/v1/auth/refresh", json={"refresh_token": "not.a.jwt"}
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or expired refresh token"


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_parses_identity_with_colon(store, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "auth_username", "admin")
    app = _build_app(store)
    app.dependency_overrides[verify_auth] = lambda: "apikey:test-key"

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/auth/me")

    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "admin"
    assert body["auth_method"] == "apikey"
    assert body["auth_identity"] == "test-key"


@pytest.mark.asyncio
async def test_me_parses_identity_without_colon(store):
    app = _build_app(store)
    app.dependency_overrides[verify_auth] = lambda: "bareidentity"

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/auth/me")

    assert resp.status_code == 200
    body = resp.json()
    assert body["auth_method"] == "unknown"
    assert body["auth_identity"] == "bareidentity"


# ---------------------------------------------------------------------------
# /setup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_already_configured_returns_403(client_with_store, monkeypatch):
    monkeypatch.setattr(auth_module.settings, "auth_password_hash", "existing-hash")

    resp = await client_with_store.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "new-password"},
    )

    assert resp.status_code == 403
    assert "already configured" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_setup_first_time_configures_password(client_with_store, monkeypatch):
    # monkeypatch stores the originals and restores them on teardown even though
    # the endpoint mutates settings directly.
    monkeypatch.setattr(auth_module.settings, "auth_password_hash", "")
    monkeypatch.setattr(auth_module.settings, "auth_username", "old")

    resp = await client_with_store.post(
        "/api/v1/auth/setup",
        json={"username": "freshadmin", "password": "fresh-password"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["username"] == "freshadmin"
    assert body["env_line"] == f'AUTH_PASSWORD_HASH="{_stub_hash("fresh-password")}"'
    # Runtime settings were mutated in place.
    assert auth_module.settings.auth_username == "freshadmin"
    assert auth_module.settings.auth_password_hash == _stub_hash("fresh-password")
