"""
Tests for the Mission Control dashboard API router (app/api/v1/dashboard.py).

The single endpoint ``GET /dashboard/summary`` aggregates six private helpers,
each reading only from ``request.app.state`` attributes or the lazily-imported
``get_policy_engine`` singleton. We drive the HTTP contract over a fresh
``FastAPI()`` with those state attributes set to ``AsyncMock``/``MagicMock`` and
``get_policy_engine`` monkeypatched — no infra, no network, no real singletons.

Awaited store/calendar methods are ``AsyncMock``; the plain attributes the
helpers read via ``getattr`` (``completed_today``, ``is_running``,
``active_count``, ``is_connected``) are set as real values so the mock never
leaks a truthy ``MagicMock`` where a scalar is expected.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import dashboard
from app.core.security import api_key_manager

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-dashboard", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app() -> FastAPI:
    """Build a FastAPI app with only the dashboard router mounted."""
    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------- fakes


def fake_store(**overrides) -> MagicMock:
    """
    Fake PromptStore whose ``list_prompts`` returns status-appropriate dicts.

    ``limit=0`` queries (activity counts) return ``{"total": N}``; the
    ``queued``/``completed`` list queries return ``{"prompts": [...]}``. Any
    kwarg override replaces the resulting attribute (e.g. to inject a
    ``side_effect`` or a non-dict return).
    """
    store = MagicMock()

    async def list_prompts(status=None, limit=None):
        if limit == 0:
            return {"total": {"pending": 4, "queued": 3, "captured": 9}.get(status, 0)}
        if status == "queued":
            return {
                "prompts": [
                    {
                        "prompt_id": "p1",
                        "content": "x" * 150,  # exercises the [:100] truncation
                        "category": "task",
                        "priority": 2,
                        "created_at": "2026-07-12T00:00:00Z",
                    },
                    {"prompt_id": "p2", "content": "second"},
                ]
            }
        if status == "completed":
            return {
                "prompts": [
                    {
                        "prompt_id": "c1",
                        "content": "done",
                        "provider_used": "ollama",
                        "model_used": "qwen",
                        "latency_ms": 12,
                        "cost_usd": 0.0,
                        "completed_at": "2026-07-12T01:00:00Z",
                    }
                ]
            }
        return {}

    store.list_prompts = AsyncMock(side_effect=list_prompts)
    for name, value in overrides.items():
        setattr(store, name, value)
    return store


def fake_executor(completed=2, failed=1, running=True, active=3) -> MagicMock:
    ex = MagicMock()
    ex.completed_today = completed
    ex.failed_today = failed
    ex.is_running = running
    ex.active_count = active
    return ex


def fake_calendar(connected=True, **overrides) -> MagicMock:
    cal = MagicMock()
    cal.is_connected = connected
    cal.get_upcoming_events = AsyncMock(
        return_value=[
            {
                "summary": "Standup",
                "start": {"dateTime": "2026-07-13T09:00:00Z"},
                "end": {"dateTime": "2026-07-13T09:30:00Z"},
            },
            {"summary": "All-day", "start": {"date": "2026-07-14"}, "end": {}},
        ]
    )
    for name, value in overrides.items():
        setattr(cal, name, value)
    return cal


def patch_budget(monkeypatch, budget: dict | None = None, raise_exc: bool = False):
    """Monkeypatch the function-local ``get_policy_engine`` import in _get_budget."""
    import app.services.frangels.policy_engine as pe

    if raise_exc:
        def boom():
            raise RuntimeError("policy engine unavailable")

        monkeypatch.setattr(pe, "get_policy_engine", boom)
        return

    engine = MagicMock()
    engine.get_status.return_value = {"budget": budget or {}}
    monkeypatch.setattr(pe, "get_policy_engine", lambda: engine)


def configure_state(app: FastAPI, **attrs) -> None:
    """Set the given ``app.state`` attributes (helpers read them via getattr)."""
    for name, value in attrs.items():
        setattr(app.state, name, value)


# ---------------------------------------------------------------- happy path


async def test_summary_full_happy_path(monkeypatch):
    patch_budget(
        monkeypatch,
        budget={
            "spent_today_usd": 1.5,
            "daily_limit_usd": 10,
            "spent_this_month_usd": 20,
            "monthly_limit_usd": 100,
        },
    )
    app = build_app()
    configure_state(
        app,
        prompt_store=fake_store(),
        prompt_executor=fake_executor(),
        prompt_agent=MagicMock(is_running=True),
        prompt_scheduler=MagicMock(is_running=True),
        google_calendar=fake_calendar(connected=True),
    )
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)

    assert resp.status_code == 200
    body = resp.json()
    # All top-level keys present.
    assert set(body) == {
        "timestamp",
        "activity",
        "budget",
        "queue_preview",
        "recent_results",
        "agents",
        "calendar_upcoming",
    }
    assert body["timestamp"].endswith("+00:00") or body["timestamp"].endswith("Z")
    # Activity: counts from the store + executor.
    assert body["activity"] == {
        "captured_today": 9,
        "processed_today": 2,
        "failed_today": 1,
        "pending": 4,
        "queued": 3,
    }
    # Budget mapped from the policy engine status.
    assert body["budget"] == {
        "daily_spent": 1.5,
        "daily_limit": 10,
        "monthly_spent": 20,
        "monthly_limit": 100,
    }
    # Queue preview: capped at 5, content truncated to 100 chars.
    assert len(body["queue_preview"]) == 2
    assert body["queue_preview"][0]["prompt_id"] == "p1"
    assert len(body["queue_preview"][0]["content"]) == 100
    assert body["queue_preview"][1]["category"] == "note"  # default applied
    # Recent results.
    assert len(body["recent_results"]) == 1
    assert body["recent_results"][0]["provider_used"] == "ollama"
    # Agents.
    assert body["agents"] == {
        "agent_running": True,
        "executor_running": True,
        "scheduler_running": True,
        "executor_active_count": 3,
    }
    # Calendar: 2 upcoming, mixing dateTime and all-day date.
    assert len(body["calendar_upcoming"]) == 2
    assert body["calendar_upcoming"][0]["start"] == "2026-07-13T09:00:00Z"
    assert body["calendar_upcoming"][1]["start"] == "2026-07-14"  # date fallback


# ---------------------------------------------------------------- empty state


async def test_summary_empty_state(monkeypatch):
    # No app.state attributes → every helper takes its "missing dependency" path.
    # Budget engine raises → zeros.
    patch_budget(monkeypatch, raise_exc=True)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)

    assert resp.status_code == 200
    body = resp.json()
    assert body["activity"] == {
        "captured_today": 0,
        "processed_today": 0,
        "failed_today": 0,
        "pending": 0,
        "queued": 0,
    }
    assert body["budget"] == {
        "daily_spent": 0,
        "daily_limit": 0,
        "monthly_spent": 0,
        "monthly_limit": 0,
    }
    assert body["queue_preview"] == []
    assert body["recent_results"] == []
    assert body["agents"] == {
        "agent_running": False,
        "executor_running": False,
        "scheduler_running": False,
        "executor_active_count": 0,
    }
    assert body["calendar_upcoming"] == []


# ---------------------------------------------------------------- activity branches


async def test_activity_store_present_no_executor(monkeypatch):
    # Store yields counts, but no executor → processed/failed stay 0.
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(app, prompt_store=fake_store())
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    body = resp.json()
    assert body["activity"]["captured_today"] == 9
    assert body["activity"]["pending"] == 4
    assert body["activity"]["processed_today"] == 0
    assert body["activity"]["failed_today"] == 0


async def test_activity_store_returns_non_dict(monkeypatch):
    # list_prompts returns a non-dict → isinstance guards skip; counts stay 0,
    # queue/recent previews fall through to [].
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(app, prompt_store=fake_store(list_prompts=AsyncMock(return_value=None)))
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    body = resp.json()
    assert body["activity"]["pending"] == 0
    assert body["activity"]["captured_today"] == 0
    assert body["queue_preview"] == []
    assert body["recent_results"] == []


async def test_activity_store_raises(monkeypatch):
    # list_prompts raises → _get_activity logs+defaults, queue/recent → [].
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(
        app,
        prompt_store=fake_store(list_prompts=AsyncMock(side_effect=RuntimeError("db down"))),
        prompt_executor=fake_executor(),
    )
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    body = resp.json()
    assert body["activity"] == {
        "captured_today": 0,
        "processed_today": 0,
        "failed_today": 0,
        "pending": 0,
        "queued": 0,
    }
    assert body["queue_preview"] == []
    assert body["recent_results"] == []


# ---------------------------------------------------------------- budget branches


async def test_budget_from_engine(monkeypatch):
    patch_budget(monkeypatch, budget={"spent_today_usd": 3.25, "daily_limit_usd": 5})
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    body = resp.json()
    assert body["budget"]["daily_spent"] == 3.25
    assert body["budget"]["daily_limit"] == 5
    assert body["budget"]["monthly_spent"] == 0  # absent key → default


async def test_budget_engine_raises(monkeypatch):
    patch_budget(monkeypatch, raise_exc=True)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    assert resp.json()["budget"] == {
        "daily_spent": 0,
        "daily_limit": 0,
        "monthly_spent": 0,
        "monthly_limit": 0,
    }


# ---------------------------------------------------------------- queue / recent


async def test_queue_and_recent_populated(monkeypatch):
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(app, prompt_store=fake_store())
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    body = resp.json()
    assert [p["prompt_id"] for p in body["queue_preview"]] == ["p1", "p2"]
    assert body["recent_results"][0]["model_used"] == "qwen"
    assert body["recent_results"][0]["latency_ms"] == 12


async def test_queue_raises_isolated(monkeypatch):
    # Only the queued-limit-5 call raises → queue [], but activity counts and
    # recent results still resolve.
    patch_budget(monkeypatch)

    async def list_prompts(status=None, limit=None):
        if limit == 5 and status == "queued":
            raise RuntimeError("boom")
        if limit == 0:
            return {"total": {"pending": 4, "queued": 3, "captured": 9}.get(status, 0)}
        if status == "completed":
            return {"prompts": [{"prompt_id": "c1"}]}
        return {}

    app = build_app()
    configure_state(
        app, prompt_store=fake_store(list_prompts=AsyncMock(side_effect=list_prompts))
    )
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    body = resp.json()
    assert body["queue_preview"] == []
    assert body["activity"]["pending"] == 4
    assert body["recent_results"] == [
        {
            "prompt_id": "c1",
            "content": "",
            "provider_used": "",
            "model_used": "",
            "latency_ms": None,
            "cost_usd": None,
            "completed_at": "",
        }
    ]


# ---------------------------------------------------------------- agents branch


async def test_agents_partial_state(monkeypatch):
    # Executor present (running), but no agent/scheduler → mixed flags.
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(app, prompt_executor=fake_executor(running=True, active=7))
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    body = resp.json()
    assert body["agents"] == {
        "agent_running": False,
        "executor_running": True,
        "scheduler_running": False,
        "executor_active_count": 7,
    }


# ---------------------------------------------------------------- calendar branches


async def test_calendar_present_not_connected(monkeypatch):
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(app, google_calendar=fake_calendar(connected=False))
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    assert resp.json()["calendar_upcoming"] == []


async def test_calendar_connected_returns_events(monkeypatch):
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(app, google_calendar=fake_calendar(connected=True))
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    upcoming = resp.json()["calendar_upcoming"]
    assert len(upcoming) == 2
    assert upcoming[0]["summary"] == "Standup"
    assert upcoming[0]["end"] == "2026-07-13T09:30:00Z"


async def test_calendar_raises(monkeypatch):
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(
        app,
        google_calendar=fake_calendar(
            connected=True,
            get_upcoming_events=AsyncMock(side_effect=RuntimeError("api error")),
        ),
    )
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    assert resp.json()["calendar_upcoming"] == []


async def test_calendar_empty_events(monkeypatch):
    # Connected but the service returns None → the ``(events or [])`` guard → [].
    patch_budget(monkeypatch)
    app = build_app()
    configure_state(
        app,
        google_calendar=fake_calendar(
            connected=True, get_upcoming_events=AsyncMock(return_value=None)
        ),
    )
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/dashboard/summary", headers=AUTH)
    assert resp.json()["calendar_upcoming"] == []


# ---------------------------------------------------------------- auth


async def test_requires_auth():
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/dashboard/summary")
    assert resp.status_code in (401, 403)
