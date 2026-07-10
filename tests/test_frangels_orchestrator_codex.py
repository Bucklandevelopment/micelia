"""
Tests for FrangelsOrchestrator (app.services.frangels.orchestrator).

The orchestrator has a single external boundary: an ``httpx.AsyncClient`` obtained
via ``self._get_client()``. Its two collaborators (``provider_store``,
``quota_manager``) are singletons attached in ``__init__`` and are replaced on the
instance with ``MagicMock`` here. The real ``ANGEL_REGISTRY`` (angels.py, ~97%
covered) is used for the HTTP-path tests (groq/gemini/…); ``select_angel`` — the
pure-logic core with the most branches — is exercised against a small, deterministic
registry patched in per test, so tier/health/privacy/capability filtering and
ordering are asserted exactly (no dependency on the real registry's contents).

Isolation: no network, no DB, no real time. The fake HTTP client's
``get/post/head`` are ``AsyncMock``s returning a ``_FakeResponse`` with a controlled
``status_code`` and ``json()``. Mirrors the mock style of
``test_provider_store_codex.py`` / ``test_quota_manager_codex.py``. ``asyncio_mode``
is ``auto`` (pyproject), so ``async def test_*`` runs without a marker.

Covers:
  - _get_client (create / reuse / recreate when closed)
  - get_configured_providers (empty + populated status; last_check None/set)
  - test_provider (unknown, no key, each per-provider _test_*, generic head
    <500/>=500/exception, outer except; angel.health mutation)
  - _test_groq/_gemini/_deepseek/_cohere/_mistral/_openrouter/_generic (200/non-200)
  - select_angel (invalid category/privacy -> defaults; filters by category, missing
    key, quota, privacy, vision/tools/min_context; empty -> None; tier/health/latency
    ordering; reasoning with/without availability; fallbacks[1:4])
  - chat (no providers, paid detour, unknown provider, no key, per-provider happy with
    record_usage+mark_used, except branch, prefer_paid success)
  - _chat_groq/_gemini/_deepseek/_openrouter/_chat_openai_compatible (200/non-200)
  - _try_paid_provider (openai ok / anthropic fallback / none)
  - _chat_paid_provider (no key, openai, anthropic, unknown, cost calc, except)
  - _chat_openai / _chat_anthropic (200/non-200, system-message split, content blocks)
  - get_frangels_orchestrator singleton
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.frangels.orchestrator as orch_module
from app.services.frangels.angels import (
    ANGEL_REGISTRY,
    Angel,
    AngelCapabilities,
    AngelCategory,
    AngelHealth,
    AngelTier,
    PrivacyLevel,
)
from app.services.frangels.orchestrator import (
    AngelSelection,
    FrangelsOrchestrator,
    InferenceResult,
    get_frangels_orchestrator,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset the module singleton and the real registry's health between tests.

    ``test_provider`` mutates ``angel.health`` on the shared ANGEL_REGISTRY, so we
    snapshot and restore a fresh AngelHealth for every angel to keep tests order
    independent.
    """
    orch_module._orchestrator = None
    saved = {pid: a.health for pid, a in ANGEL_REGISTRY.items()}
    for a in ANGEL_REGISTRY.values():
        a.health = AngelHealth()
    yield
    for pid, health in saved.items():
        ANGEL_REGISTRY[pid].health = health
    orch_module._orchestrator = None


class _FakeResponse:
    """Minimal stand-in for httpx.Response."""

    def __init__(self, status_code: int = 200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json


def _fake_client(get=None, post=None, head=None):
    """A MagicMock httpx client whose verbs are AsyncMocks returning fixed responses.

    Pass a ``_FakeResponse`` (returned) or an ``Exception`` instance (raised as
    side_effect) for any verb.
    """
    client = MagicMock()
    client.is_closed = False
    for name, value in (("get", get), ("post", post), ("head", head)):
        if isinstance(value, Exception):
            setattr(client, name, AsyncMock(side_effect=value))
        else:
            setattr(client, name, AsyncMock(return_value=value if value is not None else _FakeResponse()))
    return client


def _make_orch(api_key="secret-key", can_use=True):
    """FrangelsOrchestrator with mocked provider_store + quota_manager."""
    orch = FrangelsOrchestrator()
    orch.provider_store = MagicMock()
    orch.provider_store.get_api_key.return_value = api_key
    orch.provider_store.get_all_status.return_value = {}
    orch.quota_manager = MagicMock()
    orch.quota_manager.can_use.return_value = can_use
    return orch


def _use_client(orch, client):
    """Force ``_get_client`` to return the given fake client."""
    orch._get_client = AsyncMock(return_value=client)


def _angel(
    aid,
    category=AngelCategory.INFERENCE,
    tier=AngelTier.STANDARD,
    privacy=PrivacyLevel.MEDIUM,
    vision=False,
    tools=False,
    max_context=1000,
    models=None,
    is_available=True,
    latency=100.0,
    base_url="https://api.example/v1",
):
    """Build a controlled Angel for deterministic select_angel tests."""
    return Angel(
        id=aid,
        name=aid.title(),
        category=category,
        tier=tier,
        privacy_level=privacy,
        base_url=base_url,
        env_key="K",
        capabilities=AngelCapabilities(
            max_context_tokens=max_context,
            supports_vision=vision,
            supports_tools=tools,
            models=models if models is not None else [f"{aid}-model"],
        ),
        health=AngelHealth(is_available=is_available, latency_ms=latency),
    )


def _patch_registry(*angels):
    """Context manager patching the orchestrator's ANGEL_REGISTRY."""
    return patch.object(orch_module, "ANGEL_REGISTRY", {a.id: a for a in angels})


_OK_CHAT = {
    "choices": [{"message": {"content": "hola"}}],
    "usage": {"prompt_tokens": 5, "completion_tokens": 7},
}


# ---------------------------------------------------------------------------
# _get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    async def test_creates_and_reuses(self):
        orch = _make_orch()
        c1 = await orch._get_client()
        c2 = await orch._get_client()
        assert c1 is c2
        await c1.aclose()

    async def test_recreates_when_closed(self):
        orch = _make_orch()
        c1 = await orch._get_client()
        await c1.aclose()
        assert c1.is_closed
        c2 = await orch._get_client()
        assert c2 is not c1
        await c2.aclose()


# ---------------------------------------------------------------------------
# get_configured_providers
# ---------------------------------------------------------------------------


class TestGetConfiguredProviders:
    async def test_empty_status(self):
        orch = _make_orch()
        orch.provider_store.get_all_status.return_value = {}
        result = orch.get_configured_providers()
        assert set(result.keys()) == set(ANGEL_REGISTRY.keys())
        groq = result["groq"]
        assert groq["configured"] is False and groq["enabled"] is False
        assert groq["lastCheck"] is None
        assert groq["name"] == "Groq"

    async def test_populated_status_and_last_check(self):
        from datetime import datetime, timezone

        orch = _make_orch()
        orch.provider_store.get_all_status.return_value = {
            "groq": {"configured": True, "enabled": True}
        }
        ANGEL_REGISTRY["groq"].health.last_check = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ANGEL_REGISTRY["groq"].health.is_available = True
        result = orch.get_configured_providers()
        assert result["groq"]["configured"] is True
        assert result["groq"]["enabled"] is True
        assert result["groq"]["healthy"] is True
        assert result["groq"]["lastCheck"] == "2026-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# test_provider + _test_*
# ---------------------------------------------------------------------------


class TestTestProvider:
    async def test_unknown_provider(self):
        orch = _make_orch()
        res = await orch.test_provider("does-not-exist")
        assert res == {"healthy": False, "error": "Provider not found"}

    async def test_no_api_key(self):
        orch = _make_orch(api_key=None)
        res = await orch.test_provider("groq")
        assert res == {"healthy": False, "error": "API key not configured"}

    @pytest.mark.parametrize("provider", ["groq", "gemini", "deepseek", "cohere", "mistral", "openrouter"])
    async def test_per_provider_healthy(self, provider):
        orch = _make_orch()
        _use_client(orch, _fake_client(get=_FakeResponse(200)))
        res = await orch.test_provider(provider)
        assert res["healthy"] is True
        assert "latency_ms" in res
        # health mutated on the angel
        assert ANGEL_REGISTRY[provider].health.is_available is True
        assert ANGEL_REGISTRY[provider].health.last_check is not None

    async def test_per_provider_unhealthy_http_error(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(get=_FakeResponse(401)))
        res = await orch.test_provider("groq")
        assert res["healthy"] is False
        assert res["error"] == "HTTP 401"
        assert ANGEL_REGISTRY["groq"].health.last_error == "HTTP 401"

    async def test_generic_provider_head_ok(self):
        # huggingface hits the generic branch (not in the specific if/elif list)
        orch = _make_orch()
        _use_client(orch, _fake_client(head=_FakeResponse(204)))
        res = await orch.test_provider("huggingface")
        assert res["healthy"] is True

    async def test_generic_provider_head_server_error(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(head=_FakeResponse(500)))
        res = await orch.test_provider("huggingface")
        assert res["healthy"] is False

    async def test_generic_provider_head_exception(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(head=RuntimeError("boom")))
        res = await orch.test_provider("huggingface")
        assert res["healthy"] is False
        assert res["error"] == "Connection failed"

    async def test_outer_exception_branch(self):
        orch = _make_orch()
        orch._get_client = AsyncMock(side_effect=RuntimeError("no client"))
        res = await orch.test_provider("groq")
        assert res["healthy"] is False
        assert res["error"] == "no client"
        assert ANGEL_REGISTRY["groq"].health.is_available is False


class TestTestHelpers:
    @pytest.mark.parametrize(
        "method",
        ["_test_groq", "_test_gemini", "_test_deepseek", "_test_cohere", "_test_mistral", "_test_openrouter"],
    )
    async def test_specific_helpers_ok_and_error(self, method):
        orch = _make_orch()
        fn = getattr(orch, method)
        ok = await fn(_fake_client(get=_FakeResponse(200)), "key")
        assert ok == {"healthy": True}
        bad = await fn(_fake_client(get=_FakeResponse(503)), "key")
        assert bad == {"healthy": False, "error": "HTTP 503"}

    async def test_generic_ok_and_exception(self):
        orch = _make_orch()
        ok = await orch._test_generic(_fake_client(head=_FakeResponse(200)), "https://x", "key")
        assert ok == {"healthy": True}
        err = await orch._test_generic(_fake_client(head=ValueError("x")), "https://x", "key")
        assert err == {"healthy": False, "error": "Connection failed"}


# ---------------------------------------------------------------------------
# select_angel (pure logic, deterministic patched registry)
# ---------------------------------------------------------------------------


class TestSelectAngel:
    async def test_happy_path_orders_by_tier(self):
        orch = _make_orch()
        premium = _angel("prem", tier=AngelTier.PREMIUM, latency=50.0)
        standard = _angel("std", tier=AngelTier.STANDARD, latency=10.0)
        with _patch_registry(standard, premium):
            sel = orch.select_angel()
        assert isinstance(sel, AngelSelection)
        assert sel.angel.id == "prem"  # premium beats standard despite worse latency
        assert sel.model == "prem-model"
        assert any("prem" in r.lower() or "Prem" in r for r in sel.reasoning)
        assert sel.fallbacks and sel.fallbacks[0].id == "std"

    async def test_invalid_category_and_privacy_default(self):
        orch = _make_orch()
        a = _angel("a", tier=AngelTier.PREMIUM)
        with _patch_registry(a):
            sel = orch.select_angel(category="nonsense", privacy_required="nope")
        assert sel is not None and sel.angel.id == "a"

    async def test_category_filter_excludes(self):
        orch = _make_orch()
        db = _angel("db", category=AngelCategory.DATABASE)
        with _patch_registry(db):
            assert orch.select_angel(category="inference") is None

    async def test_missing_api_key_excludes(self):
        orch = _make_orch(api_key=None)
        a = _angel("a")
        with _patch_registry(a):
            assert orch.select_angel() is None

    async def test_quota_exhausted_excludes(self):
        orch = _make_orch(can_use=False)
        a = _angel("a")
        with _patch_registry(a):
            assert orch.select_angel() is None

    async def test_privacy_high_requirement_filters(self):
        orch = _make_orch()
        medium = _angel("m", privacy=PrivacyLevel.MEDIUM)
        high = _angel("h", privacy=PrivacyLevel.HIGH, tier=AngelTier.ECONOMY)
        with _patch_registry(medium, high):
            sel = orch.select_angel(privacy_required="high")
        assert sel is not None and sel.angel.id == "h"

    async def test_vision_and_tools_and_context_filters(self):
        orch = _make_orch()
        plain = _angel("plain", vision=False, tools=False, max_context=1000)
        rich = _angel("rich", vision=True, tools=True, max_context=100000)
        with _patch_registry(plain, rich):
            assert orch.select_angel(require_vision=True).angel.id == "rich"
            assert orch.select_angel(require_tools=True).angel.id == "rich"
            assert orch.select_angel(min_context=50000).angel.id == "rich"
            # nobody satisfies an impossible context window
            assert orch.select_angel(min_context=10**9) is None

    async def test_health_ordering_and_reasoning_without_latency(self):
        orch = _make_orch()
        up = _angel("up", is_available=True, latency=200.0)
        down = _angel("down", is_available=False, latency=1.0)
        with _patch_registry(down, up):
            sel = orch.select_angel()
        # available beats unavailable regardless of latency
        assert sel.angel.id == "up"
        assert any("Latencia" in r for r in sel.reasoning)

    async def test_fallbacks_capped_at_three(self):
        orch = _make_orch()
        angels = [_angel(f"a{i}", tier=AngelTier.STANDARD, latency=float(i)) for i in range(6)]
        with _patch_registry(*angels):
            sel = orch.select_angel()
        assert len(sel.fallbacks) == 3  # eligible[1:4]


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


class TestChat:
    async def test_no_providers_available(self):
        orch = _make_orch()
        with _patch_registry():  # empty registry -> select_angel returns None
            res = await orch.chat([{"role": "user", "content": "hi"}])
        assert isinstance(res, InferenceResult)
        assert res.success is False
        assert res.provider_id == "none"
        assert res.error == "No providers available"

    async def test_paid_provider_detour(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, {
            "content": [{"type": "text", "text": "hey"}],
            "usage": {"input_tokens": 1, "output_tokens": 2},
        })))
        res = await orch.chat([{"role": "user", "content": "hi"}], provider_id="anthropic")
        assert res.provider_id == "anthropic"
        assert res.success is True
        assert res.content == "hey"

    async def test_unknown_provider(self):
        orch = _make_orch()
        with _patch_registry(_angel("known")):
            res = await orch.chat([{"role": "user", "content": "hi"}], provider_id="ghost")
        assert res.success is False
        assert res.error == "Provider not found"

    async def test_no_api_key(self):
        orch = _make_orch(api_key=None)
        res = await orch.chat([{"role": "user", "content": "hi"}], provider_id="groq")
        assert res.success is False
        assert res.error == "API key not configured"

    async def test_groq_happy_records_usage(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, _OK_CHAT)))
        res = await orch.chat([{"role": "user", "content": "hi"}], provider_id="groq", model="llama")
        assert res.success is True
        assert res.content == "hola"
        assert res.tokens_input == 5 and res.tokens_output == 7
        orch.quota_manager.record_usage.assert_called_once()
        orch.provider_store.mark_used.assert_called_once_with("groq")

    async def test_gemini_happy(self):
        orch = _make_orch()
        gemini_body = {
            "candidates": [{"content": {"parts": [{"text": "hola-gemini"}]}}],
            "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 4},
        }
        _use_client(orch, _fake_client(post=_FakeResponse(200, gemini_body)))
        res = await orch.chat(
            [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "x"}],
            provider_id="gemini",
            model="gemini-pro",
        )
        assert res.success is True and res.content == "hola-gemini"

    async def test_openai_compatible_default_branch(self):
        # cohere is in the registry but not in chat's if/elif -> openai-compatible path
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, _OK_CHAT)))
        res = await orch.chat([{"role": "user", "content": "hi"}], provider_id="cohere", model="cmd")
        assert res.success is True and res.content == "hola"

    async def test_chat_exception_records_failure(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(post=RuntimeError("kaboom")))
        res = await orch.chat([{"role": "user", "content": "hi"}], provider_id="groq", model="m")
        assert res.success is False
        assert "kaboom" in res.error
        orch.quota_manager.record_usage.assert_called_with("groq", success=False, error="kaboom")

    async def test_auto_selects_free_provider_when_no_id(self):
        # No provider_id -> select_angel picks from the patched registry, then executes.
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, _OK_CHAT)))
        with _patch_registry(_angel("groq", models=["llama"])):
            res = await orch.chat([{"role": "user", "content": "hi"}])
        assert res.provider_id == "groq"
        assert res.success is True and res.content == "hola"
        assert res.model == "llama"
        orch.provider_store.mark_used.assert_called_once_with("groq")

    @pytest.mark.parametrize("provider", ["deepseek", "openrouter"])
    async def test_dispatch_deepseek_and_openrouter(self, provider):
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, _OK_CHAT)))
        res = await orch.chat([{"role": "user", "content": "hi"}], provider_id=provider, model="m")
        assert res.success is True and res.content == "hola"

    async def test_prefer_paid_short_circuits(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, {
            "choices": [{"message": {"content": "paid"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })))
        with patch("app.core.config.settings") as settings:
            settings.openai_api_key = "sk-openai"
            res = await orch.chat([{"role": "user", "content": "hi"}], prefer_paid=True)
        assert res.provider_id == "openai"
        assert res.success is True and res.content == "paid"


# ---------------------------------------------------------------------------
# _chat_* helpers
# ---------------------------------------------------------------------------


class TestChatHelpers:
    async def test_groq_ok_and_error(self):
        orch = _make_orch()
        ok = await orch._chat_groq(_fake_client(post=_FakeResponse(200, _OK_CHAT)), "k", "m", [])
        assert ok["success"] is True and ok["content"] == "hola"
        bad = await orch._chat_groq(_fake_client(post=_FakeResponse(500)), "k", "m", [])
        assert bad == {"success": False, "error": "HTTP 500"}

    async def test_openrouter_ok_and_error(self):
        orch = _make_orch()
        ok = await orch._chat_openrouter(_fake_client(post=_FakeResponse(200, _OK_CHAT)), "k", "m", [])
        assert ok["success"] is True
        bad = await orch._chat_openrouter(_fake_client(post=_FakeResponse(429)), "k", "m", [])
        assert bad == {"success": False, "error": "HTTP 429"}

    async def test_deepseek_delegates_to_openai_compatible(self):
        orch = _make_orch()
        res = await orch._chat_deepseek(_fake_client(post=_FakeResponse(200, _OK_CHAT)), "k", "m", [])
        assert res["success"] is True and res["content"] == "hola"

    async def test_openai_compatible_error(self):
        orch = _make_orch()
        bad = await orch._chat_openai_compatible(_fake_client(post=_FakeResponse(400)), "https://x", "k", "m", [])
        assert bad == {"success": False, "error": "HTTP 400"}

    async def test_gemini_error(self):
        orch = _make_orch()
        bad = await orch._chat_gemini(_fake_client(post=_FakeResponse(403)), "k", "m",
                                      [{"role": "user", "content": "hi"}])
        assert bad == {"success": False, "error": "HTTP 403"}


# ---------------------------------------------------------------------------
# paid providers
# ---------------------------------------------------------------------------


class TestPaidProviders:
    async def test_try_paid_uses_openai_first(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, _OK_CHAT)))
        with patch("app.core.config.settings") as settings:
            settings.openai_api_key = "sk"
            settings.anthropic_api_key = None
            res = await orch._try_paid_provider([{"role": "user", "content": "hi"}], None)
        assert res is not None and res.provider_id == "openai"

    async def test_try_paid_falls_back_to_anthropic(self):
        orch = _make_orch()

        async def fake_paid(provider_id, model, messages):
            success = provider_id == "anthropic"
            return InferenceResult(
                provider_id=provider_id, model=model or "", content="ok" if success else "",
                tokens_input=0, tokens_output=0, latency_ms=0, success=success,
                error=None if success else "fail",
            )

        orch._chat_paid_provider = AsyncMock(side_effect=fake_paid)
        with patch("app.core.config.settings") as settings:
            settings.openai_api_key = "sk"
            settings.anthropic_api_key = "sk-ant"
            res = await orch._try_paid_provider([{"role": "user", "content": "hi"}], None)
        assert res is not None and res.provider_id == "anthropic"

    async def test_try_paid_none_available(self):
        orch = _make_orch(api_key=None)
        with patch("app.core.config.settings") as settings:
            settings.openai_api_key = None
            settings.anthropic_api_key = None
            res = await orch._try_paid_provider([{"role": "user", "content": "hi"}], None)
        assert res is None

    async def test_chat_paid_no_key(self):
        orch = _make_orch(api_key=None)
        with patch("app.core.config.settings") as settings:
            settings.openai_api_key = None
            res = await orch._chat_paid_provider("openai", "gpt-4o", [{"role": "user", "content": "hi"}])
        assert res.success is False
        assert res.error == "openai API key not configured"

    async def test_chat_paid_anthropic_key_from_config(self):
        # provider_store has no key -> falls back to settings.anthropic_api_key (lines 531-532)
        orch = _make_orch(api_key=None)
        body = {
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        _use_client(orch, _fake_client(post=_FakeResponse(200, body)))
        with patch("app.core.config.settings") as settings:
            settings.anthropic_api_key = "sk-ant-config"
            res = await orch._chat_paid_provider("anthropic", "claude", [{"role": "user", "content": "hi"}])
        assert res.success is True and res.content == "hi"

    async def test_chat_paid_openai_ok_computes_cost(self):
        orch = _make_orch()
        _use_client(orch, _fake_client(post=_FakeResponse(200, _OK_CHAT)))
        res = await orch._chat_paid_provider("openai", "gpt-4o", [{"role": "user", "content": "hi"}])
        assert res.success is True and res.content == "hola"
        # cost recorded via quota_manager.record_usage(cost_usd=...)
        _, kwargs = orch.quota_manager.record_usage.call_args
        assert kwargs["cost_usd"] > 0

    async def test_chat_paid_anthropic_ok(self):
        orch = _make_orch()
        body = {
            "content": [{"type": "text", "text": "claude-says-hi"}, {"type": "other"}],
            "usage": {"input_tokens": 2, "output_tokens": 3},
        }
        _use_client(orch, _fake_client(post=_FakeResponse(200, body)))
        res = await orch._chat_paid_provider(
            "anthropic", "claude", [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
        )
        assert res.success is True and res.content == "claude-says-hi"

    async def test_chat_paid_unknown_provider(self):
        orch = _make_orch()
        _use_client(orch, _fake_client())
        res = await orch._chat_paid_provider("weirdai", "m", [{"role": "user", "content": "hi"}])
        assert res.success is False
        assert res.error == "Unknown paid provider"

    async def test_chat_paid_exception(self):
        orch = _make_orch()
        orch._get_client = AsyncMock(side_effect=RuntimeError("down"))
        res = await orch._chat_paid_provider("openai", "gpt-4o", [{"role": "user", "content": "hi"}])
        assert res.success is False and "down" in res.error


class TestOpenAIAnthropicHelpers:
    async def test_openai_ok_and_error(self):
        orch = _make_orch()
        ok = await orch._chat_openai(_fake_client(post=_FakeResponse(200, _OK_CHAT)), "k", "gpt-4o", [])
        assert ok["success"] is True and ok["content"] == "hola"
        bad = await orch._chat_openai(_fake_client(post=_FakeResponse(500)), "k", "gpt-4o", [])
        assert bad == {"success": False, "error": "OpenAI HTTP 500"}

    async def test_anthropic_splits_system_and_error(self):
        orch = _make_orch()
        body = {
            "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}],
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        ok = await orch._chat_anthropic(
            _fake_client(post=_FakeResponse(200, body)), "k", "claude",
            [{"role": "system", "content": "be nice"}, {"role": "user", "content": "hi"}],
        )
        assert ok["success"] is True and ok["content"] == "ab"
        bad = await orch._chat_anthropic(_fake_client(post=_FakeResponse(529)), "k", "claude",
                                         [{"role": "user", "content": "hi"}])
        assert bad == {"success": False, "error": "Anthropic HTTP 529"}


# ---------------------------------------------------------------------------
# singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    async def test_singleton_cached(self):
        a = get_frangels_orchestrator()
        b = get_frangels_orchestrator()
        assert a is b
        assert isinstance(a, FrangelsOrchestrator)
