"""
Tests for the Budget & Policy Engine API router (app/api/v1/budget.py).

The four endpoints obtain the policy engine through a **module-level** import
(``from app.services.frangels.policy_engine import get_policy_engine``), unlike
``agents.py``/``dashboard.py`` which read collaborators from ``app.state``. So we
monkeypatch the name already bound in the ``budget`` module namespace
(``app.api.v1.budget.get_policy_engine``) to return a ``MagicMock`` engine — the
real singleton is never constructed, no disk, no global state.

All engine methods the router touches (``get_status``, ``set_budget``,
``budget.to_dict``, ``set_category_policy``, ``evaluate``) are **synchronous**
(the router does not ``await`` them), so the fake is a plain ``MagicMock`` with
flat returns. ``evaluate`` returns a real ``PolicyDecision`` so the projected
response stays JSON-serialisable.
"""

import contextlib
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import budget
from app.core.security import api_key_manager
from app.services.frangels.policy_engine import PolicyDecision

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-budget", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app() -> FastAPI:
    """Build a FastAPI app with only the budget router mounted."""
    app = FastAPI()
    app.include_router(budget.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------- fakes


def fake_engine(**overrides) -> MagicMock:
    """PolicyEngine double; every method the router uses is synchronous."""
    engine = MagicMock()
    engine.get_status.return_value = {
        "budget": {
            "daily_limit_usd": 5.0,
            "monthly_limit_usd": 100.0,
            "spent_today_usd": 0.0,
            "spent_this_month_usd": 0.0,
            "remaining_today_usd": 5.0,
            "remaining_month_usd": 100.0,
        },
        "category_overrides": {"work": "paid-for-work"},
        "available_policies": ["free-first", "paid-for-work"],
    }
    engine.budget.to_dict.return_value = {
        "daily_limit_usd": 12.5,
        "monthly_limit_usd": 250.0,
        "spent_today_usd": 0.0,
        "spent_this_month_usd": 0.0,
        "remaining_today_usd": 12.5,
        "remaining_month_usd": 250.0,
    }
    engine.evaluate.return_value = PolicyDecision(
        prefer_paid=True,
        force_free=False,
        require_different_reviewer=True,
        budget_available=True,
        reason="Critical-reviewed: executor and reviewer on different providers",
    )
    for name, value in overrides.items():
        setattr(engine, name, value)
    return engine


@pytest.fixture
def engine(monkeypatch) -> MagicMock:
    """Patch ``get_policy_engine`` in the budget module to yield a shared fake."""
    eng = fake_engine()
    monkeypatch.setattr("app.api.v1.budget.get_policy_engine", lambda: eng)
    return eng


# ---------------------------------------------------------------- /status


async def test_status_happy(engine):
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/budget/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["budget"]["daily_limit_usd"] == 5.0
    assert body["category_overrides"] == {"work": "paid-for-work"}
    engine.get_status.assert_called_once_with()


# ---------------------------------------------------------------- /limits (PATCH)


async def test_update_limits_happy(engine):
    payload = {"daily_limit_usd": 12.5, "monthly_limit_usd": 250.0}
    async with client_for(build_app()) as ac:
        resp = await ac.patch("/api/v1/budget/limits", json=payload, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["budget"]["daily_limit_usd"] == 12.5
    engine.set_budget.assert_called_once_with(daily=12.5, monthly=250.0)


async def test_update_limits_empty_body_passes_none(engine):
    # Empty JSON object → both optional fields default to None.
    async with client_for(build_app()) as ac:
        resp = await ac.patch("/api/v1/budget/limits", json={}, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    engine.set_budget.assert_called_once_with(daily=None, monthly=None)


async def test_update_limits_partial(engine):
    # Only the daily limit provided → monthly stays None.
    async with client_for(build_app()) as ac:
        resp = await ac.patch(
            "/api/v1/budget/limits", json={"daily_limit_usd": 3.0}, headers=AUTH
        )
    assert resp.status_code == 200
    engine.set_budget.assert_called_once_with(daily=3.0, monthly=None)


# ---------------------------------------------------------------- /category-policy


async def test_category_policy_happy(engine):
    payload = {"category": "work", "policy": "paid-for-work"}
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/budget/category-policy", json=payload, headers=AUTH
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"success": True, "category": "work", "policy": "paid-for-work"}
    engine.set_category_policy.assert_called_once_with("work", "paid-for-work")


@pytest.mark.parametrize(
    "policy",
    ["free-first", "paid-for-work", "critical-reviewed", "privacy-high", "budget-cap"],
)
async def test_category_policy_accepts_every_valid_policy(engine, policy):
    payload = {"category": "note", "policy": policy}
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/budget/category-policy", json=payload, headers=AUTH
        )
    assert resp.status_code == 200
    assert resp.json()["policy"] == policy


async def test_category_policy_invalid_400(engine):
    payload = {"category": "work", "policy": "not-a-real-policy"}
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/budget/category-policy", json=payload, headers=AUTH
        )
    assert resp.status_code == 400
    assert "Invalid policy" in resp.json()["detail"]
    engine.set_category_policy.assert_not_called()


async def test_category_policy_missing_field_422(engine):
    # Missing required ``policy`` → Pydantic validation fails before the body runs.
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/budget/category-policy", json={"category": "work"}, headers=AUTH
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------- /evaluate


async def test_evaluate_defaults(engine):
    # No query params → router uses category="note", provider_policy="free-first".
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/budget/evaluate", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "prefer_paid": True,
        "force_free": False,
        "require_different_reviewer": True,
        "budget_available": True,
        "reason": "Critical-reviewed: executor and reviewer on different providers",
    }
    engine.evaluate.assert_called_once_with(
        {"category": "note", "provider_policy": "free-first"}
    )


async def test_evaluate_explicit_query(engine):
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/budget/evaluate",
            params={"category": "work", "provider_policy": "paid-for-work"},
            headers=AUTH,
        )
    assert resp.status_code == 200
    engine.evaluate.assert_called_once_with(
        {"category": "work", "provider_policy": "paid-for-work"}
    )


# ---------------------------------------------------------------- auth


async def test_requires_auth():
    # No API key on any endpoint → verify_auth rejects before the body runs.
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/budget/status")
    assert resp.status_code in (401, 403)
