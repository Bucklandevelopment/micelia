"""
Tests for the Frangels API router (app/api/v1/frangels.py).

The 15 endpoints reach their collaborators through **module-level** imports
(``from app.services.frangels.provider_store import get_provider_store`` and
siblings), so we monkeypatch the names already bound in the ``frangels`` module
namespace (``app.api.v1.frangels.get_provider_store`` /
``...get_quota_manager`` / ``...get_frangels_orchestrator``). The real
singletons — which touch encrypted disk storage and the ngrok/httpx-backed
orchestrator — are never constructed: no disk, no network, no ``.env``.

``ANGEL_REGISTRY``, ``AngelCategory`` and ``PrivacyLevel`` are used **real**
(the router iterates the registry and coerces the privacy string), so the fakes
only stand in for the three service singletons.

Store / quota-manager methods the router touches are all **synchronous** →
plain ``MagicMock``. Only the orchestrator's ``chat`` / ``test_provider`` are
``await``ed → ``AsyncMock``. Dataclasses returned by the router unchanged
(``QuotaStatus``, ``InferenceResult``) are built **real** so ``asdict`` / the
JSON projection stay serialisable.
"""

import contextlib
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import frangels
from app.core.security import api_key_manager
from app.services.frangels.orchestrator import InferenceResult
from app.services.frangels.quota_manager import QuotaStatus

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-frangels", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}

# A provider guaranteed present in the real registry (inference / premium).
KNOWN = "groq"
UNKNOWN = "definitely-not-a-real-provider"


def build_app() -> FastAPI:
    """Build a FastAPI app with only the frangels router mounted."""
    app = FastAPI()
    app.include_router(frangels.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------- fakes


@dataclass
class FakeCred:
    """Minimal ProviderCredential stand-in — the router only reads ``enabled``."""

    enabled: bool = True


def make_quota(provider_id: str = KNOWN, *, percentage: float = 10.0,
               is_exhausted: bool = False) -> QuotaStatus:
    return QuotaStatus(
        provider_id=provider_id,
        provider_name=provider_id.title(),
        category="inference",
        used=int(percentage),
        limit=100,
        unit="requests/day",
        percentage=percentage,
        reset_time="2026-07-14T00:00:00Z",
        is_exhausted=is_exhausted,
    )


def make_result() -> InferenceResult:
    return InferenceResult(
        provider_id=KNOWN,
        model="llama-3.1-70b",
        content="hello from groq",
        tokens_input=11,
        tokens_output=7,
        latency_ms=42.0,
        success=True,
    )


@pytest.fixture
def store() -> MagicMock:
    """Synchronous provider-store double."""
    s = MagicMock()
    s.get_all_status.return_value = {}
    s.get.return_value = FakeCred(enabled=True)
    s.list_configured.return_value = {}
    s.export_to_env.return_value = {}
    return s


@pytest.fixture
def quota() -> MagicMock:
    """Synchronous quota-manager double."""
    q = MagicMock()
    q.get_quota_status.return_value = None
    q.get_all_quotas.return_value = []
    q.get_usage_stats.return_value = {
        "today": {"requests": 3, "tokens": 1500, "cost_equivalent_usd": 0.003},
        "thisMonth": {"requests": 40, "tokens": 20000, "cost_equivalent_usd": 0.04},
        "quotas": [],
    }
    q.can_use.return_value = True
    return q


@pytest.fixture
def orch() -> MagicMock:
    """Orchestrator double — only chat/test_provider are awaited."""
    o = MagicMock()
    o.chat = AsyncMock(return_value=make_result())
    o.test_provider = AsyncMock(return_value={
        "provider_id": KNOWN, "success": True, "latency_ms": 30.0,
    })
    return o


@pytest.fixture
def wired(monkeypatch, store, quota, orch):
    """Patch the three module-level singleton getters to the shared fakes."""
    monkeypatch.setattr("app.api.v1.frangels.get_provider_store", lambda: store)
    monkeypatch.setattr("app.api.v1.frangels.get_quota_manager", lambda: quota)
    monkeypatch.setattr(
        "app.api.v1.frangels.get_frangels_orchestrator", lambda: orch
    )
    return store, quota, orch


# ---------------------------------------------------------------- GET /providers


async def test_list_providers_happy(wired, store, quota):
    # One provider configured; quota present for KNOWN, None for the rest →
    # exercises both the ``quota`` ternary and the ``... else None`` branch.
    store.get_all_status.return_value = {
        KNOWN: {"configured": True, "enabled": True, "last_used": "2026-07-13"}
    }
    quota.get_quota_status.side_effect = (
        lambda pid: make_quota(pid) if pid == KNOWN else None
    )
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/frangels/providers", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"]["total"] == len(frangels.ANGEL_REGISTRY)
    assert body["summary"]["configured"] == 1
    assert body["summary"]["enabled"] == 1
    # by_category buckets exist and the groq entry landed under inference.
    assert set(body["by_category"]) == {"inference", "gpu", "database", "infra"}
    groq = next(p for p in body["providers"] if p["id"] == KNOWN)
    assert groq["configured"] is True
    assert groq["quota"]["percentage"] == 10.0


# ---------------------------------------------------------------- GET /providers/{id}


async def test_get_provider_not_found(wired):
    async with client_for(build_app()) as ac:
        resp = await ac.get(f"/api/v1/frangels/providers/{UNKNOWN}", headers=AUTH)
    assert resp.status_code == 404
    assert UNKNOWN in resp.json()["detail"]


async def test_get_provider_happy_with_quota(wired, store, quota):
    store.get_all_status.return_value = {
        KNOWN: {"configured": True, "enabled": False, "created_at": "x"}
    }
    quota.get_quota_status.return_value = make_quota()
    async with client_for(build_app()) as ac:
        resp = await ac.get(f"/api/v1/frangels/providers/{KNOWN}", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == KNOWN
    assert body["configured"] is True
    assert body["quota_status"]["percentage"] == 10.0
    assert isinstance(body["capabilities"], dict)  # asdict projection


async def test_get_provider_happy_without_quota(wired, quota):
    quota.get_quota_status.return_value = None
    async with client_for(build_app()) as ac:
        resp = await ac.get(f"/api/v1/frangels/providers/{KNOWN}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["quota_status"] is None


# ---------------------------------------------------------------- POST /providers


async def test_save_credentials_happy(wired, store):
    payload = {"provider_id": KNOWN, "api_key": "  sk-abc123  ", "extra_key": " ex "}
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/providers", json=payload, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    store.set.assert_called_once_with(
        provider_id=KNOWN, api_key="sk-abc123", extra_key="ex", enabled=True
    )


async def test_save_credentials_unknown_provider_400(wired, store):
    payload = {"provider_id": UNKNOWN, "api_key": "sk-abc"}
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/providers", json=payload, headers=AUTH)
    assert resp.status_code == 400
    assert "Unknown provider" in resp.json()["detail"]
    store.set.assert_not_called()


async def test_save_credentials_empty_key_400(wired, store):
    payload = {"provider_id": KNOWN, "api_key": "   "}
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/providers", json=payload, headers=AUTH)
    assert resp.status_code == 400
    assert "API key cannot be empty" in resp.json()["detail"]
    store.set.assert_not_called()


async def test_save_credentials_missing_field_422(wired):
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/frangels/providers", json={"provider_id": KNOWN}, headers=AUTH
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------- DELETE /providers/{id}


async def test_delete_credentials_happy(wired, store):
    async with client_for(build_app()) as ac:
        resp = await ac.delete(f"/api/v1/frangels/providers/{KNOWN}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    store.delete.assert_called_once_with(KNOWN)


async def test_delete_credentials_unknown_404(wired, store):
    async with client_for(build_app()) as ac:
        resp = await ac.delete(f"/api/v1/frangels/providers/{UNKNOWN}", headers=AUTH)
    assert resp.status_code == 404
    store.delete.assert_not_called()


# ---------------------------------------------------------------- PATCH /providers/{id}/toggle


async def test_toggle_unknown_404(wired):
    async with client_for(build_app()) as ac:
        resp = await ac.patch(
            f"/api/v1/frangels/providers/{UNKNOWN}/toggle",
            json={"enabled": True}, headers=AUTH,
        )
    assert resp.status_code == 404


async def test_toggle_not_configured_400(wired, store):
    store.get.return_value = None
    async with client_for(build_app()) as ac:
        resp = await ac.patch(
            f"/api/v1/frangels/providers/{KNOWN}/toggle",
            json={"enabled": True}, headers=AUTH,
        )
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"]


async def test_toggle_enable(wired, store):
    async with client_for(build_app()) as ac:
        resp = await ac.patch(
            f"/api/v1/frangels/providers/{KNOWN}/toggle",
            json={"enabled": True}, headers=AUTH,
        )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True
    store.enable.assert_called_once_with(KNOWN)
    store.disable.assert_not_called()


async def test_toggle_disable(wired, store):
    async with client_for(build_app()) as ac:
        resp = await ac.patch(
            f"/api/v1/frangels/providers/{KNOWN}/toggle",
            json={"enabled": False}, headers=AUTH,
        )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    store.disable.assert_called_once_with(KNOWN)
    store.enable.assert_not_called()


# ---------------------------------------------------------------- POST /providers/{id}/test


async def test_test_provider_unknown_404(wired, orch):
    async with client_for(build_app()) as ac:
        resp = await ac.post(f"/api/v1/frangels/providers/{UNKNOWN}/test", headers=AUTH)
    assert resp.status_code == 404
    orch.test_provider.assert_not_called()


async def test_test_provider_happy(wired, orch):
    async with client_for(build_app()) as ac:
        resp = await ac.post(f"/api/v1/frangels/providers/{KNOWN}/test", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    orch.test_provider.assert_awaited_once_with(KNOWN)


async def test_test_provider_exception_returns_error_dict(wired, orch):
    orch.test_provider.side_effect = RuntimeError("boom")
    async with client_for(build_app()) as ac:
        resp = await ac.post(f"/api/v1/frangels/providers/{KNOWN}/test", headers=AUTH)
    # The except branch swallows and returns a 200 body with success=False.
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"] == "boom"
    assert body["latency_ms"] == 0


# ---------------------------------------------------------------- GET /usage


async def test_usage_delegates(wired, quota):
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/frangels/usage", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["today"]["requests"] == 3
    quota.get_usage_stats.assert_called_once_with()


# ---------------------------------------------------------------- GET /quotas


async def test_quotas_summary(wired, quota):
    quota.get_all_quotas.return_value = [
        make_quota("a", percentage=100.0, is_exhausted=True),
        make_quota("b", percentage=85.0),   # warning band [80,100)
        make_quota("c", percentage=10.0),
    ]
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/frangels/quotas", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["summary"] == {"total": 3, "exhausted": 1, "warning": 1}
    assert len(body["quotas"]) == 3


# ---------------------------------------------------------------- GET /quotas/{id}


async def test_provider_quota_not_found(wired, quota):
    quota.get_quota_status.return_value = None
    async with client_for(build_app()) as ac:
        resp = await ac.get(f"/api/v1/frangels/quotas/{KNOWN}", headers=AUTH)
    assert resp.status_code == 404


async def test_provider_quota_happy(wired, quota):
    quota.get_quota_status.return_value = make_quota()
    async with client_for(build_app()) as ac:
        resp = await ac.get(f"/api/v1/frangels/quotas/{KNOWN}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["percentage"] == 10.0


# ---------------------------------------------------------------- POST /chat


CHAT_BODY = {"messages": [{"role": "user", "content": "hi"}]}


async def test_chat_happy(wired, orch):
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/chat", json=CHAT_BODY, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == KNOWN
    assert body["message"] == {"role": "assistant", "content": "hello from groq"}
    assert body["usage"]["total_tokens"] == 18
    assert body["cached"] is False
    orch.chat.assert_awaited_once()


async def test_chat_valid_privacy_level_coerced(wired, orch):
    body = {**CHAT_BODY, "privacy_level": "high"}
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/chat", json=body, headers=AUTH)
    assert resp.status_code == 200
    # The valid string is coerced to PrivacyLevel.HIGH and passed as min_privacy.
    assert orch.chat.await_args.kwargs["min_privacy"] == frangels.PrivacyLevel.HIGH


async def test_chat_invalid_privacy_level_ignored(wired, orch):
    body = {**CHAT_BODY, "privacy_level": "not-a-level"}
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/chat", json=body, headers=AUTH)
    # ValueError swallowed → min_privacy stays None, request still succeeds.
    assert resp.status_code == 200
    assert orch.chat.await_args.kwargs["min_privacy"] is None


async def test_chat_orchestrator_error_502(wired, orch):
    orch.chat.side_effect = RuntimeError("upstream down")
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/chat", json=CHAT_BODY, headers=AUTH)
    assert resp.status_code == 502
    assert "upstream down" in resp.json()["detail"]


# ---------------------------------------------------------------- GET /chat/available-providers


async def test_available_chat_providers_filters_and_sorts(wired, store, quota):
    # Enable two inference providers of different tiers plus a GPU provider
    # (skipped by category) and a disabled/exhausted one (skipped by the
    # cred/can_use guards). Result must contain only the two enabled+available,
    # ordered premium-before-standard.
    # mistral is enabled at the cred layer but exhausted at can_use → it must
    # reach and hit the ``can_use`` guard (line 403), not be pre-filtered.
    enabled = {"groq", "deepseek", "mistral"}   # premium, standard, standard

    def cred_for(pid):
        if pid == "gemini":
            return FakeCred(enabled=False)  # inference but disabled → skip
        return FakeCred(enabled=True) if pid in enabled else None

    store.get.side_effect = cred_for
    quota.can_use.side_effect = lambda pid: pid != "mistral"  # exhausted → skip

    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/frangels/chat/available-providers", headers=AUTH
        )
    assert resp.status_code == 200
    body = resp.json()
    ids = [p["id"] for p in body["providers"]]
    assert ids == ["groq", "deepseek"]      # premium first
    assert body["count"] == 2


# ---------------------------------------------------------------- GET /status


async def test_status_aggregates(wired, store, quota):
    store.list_configured.return_value = {KNOWN: True, "gemini": False, "kaggle": True}
    quota.can_use.return_value = True
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/frangels/status", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "operational"
    assert body["providers"]["configured"] == 3
    assert body["providers"]["enabled"] == 2          # groq + kaggle
    # groq→inference, kaggle→gpu are enabled + can_use.
    assert body["providers"]["available_by_category"]["inference"] == 1
    assert body["providers"]["available_by_category"]["gpu"] == 1
    assert body["usage"]["today"]["requests"] == 3


# ---------------------------------------------------------------- POST /sync-env


async def test_sync_env_reports_imported_delta(wired, store):
    # list_configured is called before and after sync_from_env → simulate growth.
    store.list_configured.side_effect = [
        {KNOWN: True},                       # before: 1
        {KNOWN: True, "gemini": True, "cohere": True},  # after: 3
    ]
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/frangels/sync-env", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 2
    assert body["total_configured"] == 3
    store.sync_from_env.assert_called_once_with()


# ---------------------------------------------------------------- GET /export-env


async def test_export_env_masks_both_branches(wired, store):
    store.export_to_env.return_value = {
        "GROQ_API_KEY": "sk-1234567890abcd",  # len 16 (>8) → partial mask
        "TINY_KEY": "abc",                    # len 3 (<=8) → full mask
    }
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/frangels/export-env", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    long = body["env_vars"]["GROQ_API_KEY"]
    assert long.startswith("sk-1") and long.endswith("abcd") and "*" in long
    assert body["env_vars"]["TINY_KEY"] == "***"


# ---------------------------------------------------------------- auth


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v1/frangels/providers"),
        ("get", f"/api/v1/frangels/providers/{KNOWN}"),
        ("post", "/api/v1/frangels/providers"),
        ("get", "/api/v1/frangels/usage"),
        ("get", "/api/v1/frangels/quotas"),
        ("post", "/api/v1/frangels/chat"),
        ("get", "/api/v1/frangels/status"),
        ("post", "/api/v1/frangels/sync-env"),
        ("get", "/api/v1/frangels/export-env"),
    ],
)
async def test_requires_auth(wired, method, path):
    async with client_for(build_app()) as ac:
        resp = await getattr(ac, method)(path)
    assert resp.status_code in (401, 403)
