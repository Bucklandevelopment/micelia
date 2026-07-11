"""
Integration test of the register → login funnel with the REAL bcrypt boundary.

`test_auth_endpoints_codex.py` covers every branch of app/api/v1/auth.py but
deliberately *stubs* `pwd_context.hash/verify` — so it proves the endpoint control
flow while saying nothing about whether password hashing actually works at runtime.
That gap hid a real bug: with bcrypt >=4.1 (the venv shipped 5.0.0), passlib 1.7.4's
backend probe raised `ValueError: password cannot be longer than 72 bytes` on the
first hash, i.e. `POST /auth/register` and real-user login returned 500 in production.

This file closes that gap. It runs `pwd_context` for real (no stub) and drives the
full round trip: register hashes a password with real bcrypt and stores the hash,
then login verifies the plaintext against that stored hash with real bcrypt. It
FAILS on bcrypt 5.0.0 and PASSES once bcrypt is pinned to 4.0.1 — it is the
executable proof of that fix.

No DB and no network: `UserModel` uses a Postgres-only UUID column (won't compile on
SQLite) and aiosqlite is not installed, so a real store is out of scope for a
hermetic `make verify`. A tiny stateful in-memory fake stands in for `user_store`;
it stores the exact `password_hash` handed to `create_user` and returns it from
`get_user_by_email(..., include_hash=True)`, mirroring the real store's contract so
the crypto round trip is exercised through the real endpoints.
"""

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import auth as auth_module
from app.core.security import jwt_auth
from app.services.user_store import DuplicateEmailError

_EMAIL = "Funnel.User@Example.com"
_PASSWORD = "correct-horse-battery"


class _StatefulUserStore:
    """In-memory stand-in for UserStore that really stores the bcrypt hash."""

    def __init__(self) -> None:
        self._by_email: dict[str, dict] = {}
        self.touched: list[UUID] = []

    async def create_user(
        self, email: str, password_hash: str, plan_code: str = "free"
    ) -> dict:
        normalized = email.strip().lower()
        if normalized in self._by_email:
            raise DuplicateEmailError(normalized)
        record = {
            "user_id": str(uuid4()),
            "email": normalized,
            "password_hash": password_hash,
            "is_active": True,
            "is_verified": False,
            "plan_code": plan_code,
        }
        self._by_email[normalized] = record
        return {k: v for k, v in record.items() if k != "password_hash"}

    async def get_user_by_email(
        self, email: str, *, include_hash: bool = False
    ) -> dict | None:
        record = self._by_email.get(email.strip().lower())
        if record is None:
            return None
        if include_hash:
            return dict(record)
        return {k: v for k, v in record.items() if k != "password_hash"}

    async def touch_last_login(self, user_id: UUID) -> None:
        self.touched.append(user_id)


def _build_app(store: _StatefulUserStore) -> FastAPI:
    app = FastAPI()
    app.state.user_store = store
    app.state.event_store = None  # audit_logger stays a no-op (None-safe)
    app.include_router(auth_module.router, prefix="/api/v1")
    return app


@pytest.fixture()
def store() -> _StatefulUserStore:
    return _StatefulUserStore()


@pytest.fixture()
async def client(store):
    app = _build_app(store)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# register — real hashing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_stores_a_real_bcrypt_hash(client, store):
    resp = await client.post(
        "/api/v1/auth/register", json={"email": _EMAIL, "password": _PASSWORD}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]

    # The stored hash is a genuine bcrypt hash of the password — not the plaintext,
    # not a stub. This is exactly what the mocked endpoint test could not assert.
    (record,) = store._by_email.values()
    stored = record["password_hash"]
    assert stored.startswith("$2b$")
    assert stored != _PASSWORD
    # And the access-token subject is the freshly minted user_id (auto-login).
    assert jwt_auth.decode_token(body["access_token"])["sub"] == record["user_id"]


# ---------------------------------------------------------------------------
# register → login round trip — real verify
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_then_login_round_trip(client, store):
    reg = await client.post(
        "/api/v1/auth/register", json={"email": _EMAIL, "password": _PASSWORD}
    )
    assert reg.status_code == 201
    user_id = jwt_auth.decode_token(reg.json()["access_token"])["sub"]

    # login uses the `username` field for the email; real bcrypt verifies the
    # plaintext against the stored $2b$ hash.
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": _EMAIL, "password": _PASSWORD},
    )

    assert login.status_code == 200
    assert jwt_auth.decode_token(login.json()["access_token"])["sub"] == user_id
    # touch_last_login received the user's UUID.
    assert store.touched and str(store.touched[0]) == user_id


@pytest.mark.asyncio
async def test_login_wrong_password_is_rejected(client, store, monkeypatch):
    # Register a user, then log in with the wrong password. The registered-user
    # branch must reject it (real verify returns False) and, with no admin
    # fallback configured to match, the endpoint returns 401.
    await client.post(
        "/api/v1/auth/register", json={"email": _EMAIL, "password": _PASSWORD}
    )
    monkeypatch.setattr(auth_module.settings, "auth_username", "unrelated-admin")
    monkeypatch.setattr(auth_module.jwt_auth, "verify_password", lambda _pw: False)

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": _EMAIL, "password": "not-the-password"},
    )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"
    assert store.touched == []


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    first = await client.post(
        "/api/v1/auth/register", json={"email": _EMAIL, "password": _PASSWORD}
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register",
        json={"email": _EMAIL.upper(), "password": "another-password"},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Email already registered"
