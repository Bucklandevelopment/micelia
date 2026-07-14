"""
Tests for the prompts API router (app/api/v1/prompts.py).

Each test mounts the router on a fresh FastAPI app and injects an AsyncMock
``prompt_store`` (and, for the pipeline endpoints, mock agent/executor) into
``app.state``. No DB, HTTP, subprocess or macOS dependency is exercised — the
service layer (PromptStore) is already covered by test_prompt_store_codex.py, so
here we only drive the HTTP contract of the router.
"""

import contextlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import prompts
from app.core.security import api_key_manager

# A dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-prompts", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}

_UNSET = object()


def build_app(store=_UNSET, *, agent=_UNSET, executor=_UNSET) -> FastAPI:
    """Build a FastAPI app with only the prompts router and injected state."""
    app = FastAPI()
    app.include_router(prompts.router, prefix="/api/v1")
    app.state.prompt_store = AsyncMock() if store is _UNSET else store
    if agent is not _UNSET:
        app.state.prompt_agent = agent
    if executor is not _UNSET:
        app.state.prompt_executor = executor
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def _store(**methods) -> AsyncMock:
    """AsyncMock store with the given awaitable method return values preset."""
    store = AsyncMock()
    for name, value in methods.items():
        getattr(store, name).return_value = value
    return store


# ==================== CRUD ====================


async def test_create_prompt():
    pid = uuid4()
    app = build_app(_store(create_prompt=pid))
    async with client_for(app) as c:
        r = await c.post("/api/v1/prompts", json={"content": "hola"}, headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body == {"prompt_id": str(pid), "status": "pending"}


async def test_create_prompt_full_payload():
    pid = uuid4()
    store = _store(create_prompt=pid)
    app = build_app(store)
    payload = {
        "content": "algo",
        "category": "task",
        "priority": 8,
        "tags": ["a", "b"],
        "prefer_paid": True,
        "metadata": {"k": "v"},
    }
    async with client_for(app) as c:
        r = await c.post("/api/v1/prompts", json=payload, headers=AUTH)
    assert r.status_code == 200
    store.create_prompt.assert_awaited_once()
    assert store.create_prompt.await_args.kwargs["priority"] == 8


async def test_create_prompt_priority_out_of_range_422():
    app = build_app()
    async with client_for(app) as c:
        r = await c.post(
            "/api/v1/prompts", json={"content": "x", "priority": 99}, headers=AUTH
        )
    assert r.status_code == 422


async def test_list_prompts_with_filters():
    rows = [{"prompt_id": str(uuid4()), "content": "x"}]
    store = _store(list_prompts=rows)
    app = build_app(store)
    async with client_for(app) as c:
        r = await c.get(
            "/api/v1/prompts?status=pending&category=note&limit=10&offset=5",
            headers=AUTH,
        )
    assert r.status_code == 200
    assert r.json() == rows
    assert store.list_prompts.await_args.kwargs["status"] == "pending"
    assert store.list_prompts.await_args.kwargs["limit"] == 10


async def test_list_prompts_limit_over_cap_422():
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts?limit=500", headers=AUTH)
    assert r.status_code == 422


async def test_get_stats():
    app = build_app(_store(get_stats={"total": 3}))
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/stats", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"total": 3}


# ==================== INBOX / STAGING / ARCHIVE ====================


async def test_get_inbox():
    app = build_app(_store(get_captured_prompts=[{"id": 1}]))
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/inbox?limit=5", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"prompts": [{"id": 1}], "view": "inbox"}


async def test_get_staging():
    app = build_app(_store(get_staged_prompts=[{"id": 2}]))
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/staging", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"prompts": [{"id": 2}], "view": "staging"}


async def test_get_archive():
    app = build_app(_store(get_archived_prompts={"prompts": [], "total": 0}))
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/archive?limit=5&offset=0", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"prompts": [], "total": 0}


# ==================== DETAIL / UPDATE / DELETE ====================


async def test_get_prompt_ok():
    pid = uuid4()
    app = build_app(_store(get_prompt={"prompt_id": str(pid), "status": "pending"}))
    async with client_for(app) as c:
        r = await c.get(f"/api/v1/prompts/{pid}", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


async def test_get_prompt_not_found():
    app = build_app(_store(get_prompt=None))
    async with client_for(app) as c:
        r = await c.get(f"/api/v1/prompts/{uuid4()}", headers=AUTH)
    assert r.status_code == 404


async def test_get_prompt_bad_uuid_422():
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/not-a-uuid", headers=AUTH)
    assert r.status_code == 422


async def test_update_prompt_ok():
    store = _store(update_prompt=True)
    app = build_app(store)
    async with client_for(app) as c:
        r = await c.patch(
            f"/api/v1/prompts/{uuid4()}", json={"priority": 3}, headers=AUTH
        )
    assert r.status_code == 200
    assert r.json() == {"success": True}


async def test_update_prompt_no_fields_400():
    app = build_app()
    async with client_for(app) as c:
        r = await c.patch(f"/api/v1/prompts/{uuid4()}", json={}, headers=AUTH)
    assert r.status_code == 400


async def test_update_prompt_not_found():
    app = build_app(_store(update_prompt=False))
    async with client_for(app) as c:
        r = await c.patch(
            f"/api/v1/prompts/{uuid4()}", json={"content": "x"}, headers=AUTH
        )
    assert r.status_code == 404


async def test_delete_prompt_ok():
    app = build_app(_store(delete_prompt=True))
    async with client_for(app) as c:
        r = await c.delete(f"/api/v1/prompts/{uuid4()}", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True}


async def test_delete_prompt_not_found():
    app = build_app(_store(delete_prompt=False))
    async with client_for(app) as c:
        r = await c.delete(f"/api/v1/prompts/{uuid4()}", headers=AUTH)
    assert r.status_code == 404


# ==================== QUICK NOTES ====================


async def test_create_note():
    pid = uuid4()
    app = build_app(_store(create_note=pid))
    async with client_for(app) as c:
        r = await c.post(
            "/api/v1/prompts/notes", json={"text": "recordar"}, headers=AUTH
        )
    assert r.status_code == 200
    assert r.json() == {"prompt_id": str(pid), "status": "captured"}


# ==================== RETRY ====================


async def test_retry_ok():
    store = _store(
        get_prompt={"status": "failed", "iterations": 2}, update_prompt=True
    )
    app = build_app(store)
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/retry", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "pending"}
    assert store.update_prompt.await_args.kwargs["iterations"] == 3


async def test_retry_not_found():
    app = build_app(_store(get_prompt=None))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/retry", headers=AUTH)
    assert r.status_code == 404


async def test_retry_bad_status_400():
    app = build_app(_store(get_prompt={"status": "pending", "iterations": 0}))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/retry", headers=AUTH)
    assert r.status_code == 400


# ==================== CLASSIFY / STAGE / APPROVE / ARCHIVE ====================


async def test_classify_ok():
    store = _store(get_prompt={"status": "captured"}, classify_prompt=True)
    app = build_app(store)
    async with client_for(app) as c:
        r = await c.post(
            f"/api/v1/prompts/{uuid4()}/classify",
            json={"category": "task", "tags": ["x"]},
            headers=AUTH,
        )
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "classified"}


async def test_classify_not_found():
    app = build_app(_store(get_prompt=None))
    async with client_for(app) as c:
        r = await c.post(
            f"/api/v1/prompts/{uuid4()}/classify",
            json={"category": "task"},
            headers=AUTH,
        )
    assert r.status_code == 404


async def test_classify_wrong_status_400():
    app = build_app(_store(get_prompt={"status": "pending"}))
    async with client_for(app) as c:
        r = await c.post(
            f"/api/v1/prompts/{uuid4()}/classify",
            json={"category": "task"},
            headers=AUTH,
        )
    assert r.status_code == 400


async def test_stage_ok():
    app = build_app(_store(stage_prompt=True))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/stage", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "staged"}


async def test_stage_not_found():
    app = build_app(_store(stage_prompt=False))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/stage", headers=AUTH)
    assert r.status_code == 404


async def test_approve_ok():
    app = build_app(_store(approve_staged=True))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/approve", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "pending"}


async def test_approve_not_found():
    app = build_app(_store(approve_staged=False))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/approve", headers=AUTH)
    assert r.status_code == 404


async def test_archive_ok():
    app = build_app(_store(archive_prompt=True))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/archive", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "archived"}


async def test_archive_not_found():
    app = build_app(_store(archive_prompt=False))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/archive", headers=AUTH)
    assert r.status_code == 404


# ==================== PROMOTION ====================


async def test_promote_to_list_ok():
    app = build_app(_store(promote_to_list=True))
    async with client_for(app) as c:
        r = await c.post(
            f"/api/v1/prompts/{uuid4()}/promote/list",
            json={"list_slug": "ideas"},
            headers=AUTH,
        )
    assert r.status_code == 200
    assert r.json() == {"success": True, "promoted_to": "list", "ref": "ideas"}


async def test_promote_to_list_not_found():
    app = build_app(_store(promote_to_list=False))
    async with client_for(app) as c:
        r = await c.post(
            f"/api/v1/prompts/{uuid4()}/promote/list",
            json={"list_slug": "ideas"},
            headers=AUTH,
        )
    assert r.status_code == 404


async def test_promote_to_skill_ok():
    skill_id = uuid4()
    app = build_app(_store(promote_to_skill=skill_id))
    async with client_for(app) as c:
        r = await c.post(
            f"/api/v1/prompts/{uuid4()}/promote/skill",
            json={"name": "s", "trigger_pattern": "^go"},
            headers=AUTH,
        )
    assert r.status_code == 200
    assert r.json() == {
        "success": True,
        "promoted_to": "skill",
        "skill_id": str(skill_id),
    }


async def test_promote_to_skill_not_found():
    app = build_app(_store(promote_to_skill=None))
    async with client_for(app) as c:
        r = await c.post(
            f"/api/v1/prompts/{uuid4()}/promote/skill",
            json={"name": "s", "trigger_pattern": "^go"},
            headers=AUTH,
        )
    assert r.status_code == 404


async def test_promote_to_mcp_ok():
    app = build_app(_store(promote_to_mcp=True))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/promote/mcp", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "promoted_to": "mcp"}


async def test_promote_to_mcp_not_found():
    app = build_app(_store(promote_to_mcp=False))
    async with client_for(app) as c:
        r = await c.post(f"/api/v1/prompts/{uuid4()}/promote/mcp", headers=AUTH)
    assert r.status_code == 404


# ==================== PROMPT LISTS ====================


async def test_create_list():
    lid = uuid4()
    app = build_app(_store(create_list=lid))
    async with client_for(app) as c:
        r = await c.post(
            "/api/v1/prompts/lists", json={"name": "mi lista"}, headers=AUTH
        )
    assert r.status_code == 200
    assert r.json() == {"list_id": str(lid)}


async def test_list_all_lists():
    app = build_app(_store(list_all_lists=[{"slug": "a"}, {"slug": "b"}]))
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/lists", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"lists": [{"slug": "a"}, {"slug": "b"}], "count": 2}


async def test_get_list_ok():
    app = build_app(_store(get_list={"slug": "ideas", "items": []}))
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/lists/ideas", headers=AUTH)
    assert r.status_code == 200
    assert r.json()["slug"] == "ideas"


async def test_get_list_not_found():
    app = build_app(_store(get_list=None))
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/lists/none", headers=AUTH)
    assert r.status_code == 404


async def test_update_list_ok():
    app = build_app(_store(update_list=True))
    async with client_for(app) as c:
        r = await c.patch(
            "/api/v1/prompts/lists/ideas",
            json={"description": "nueva"},
            headers=AUTH,
        )
    assert r.status_code == 200
    assert r.json() == {"success": True}


async def test_update_list_no_fields_400():
    app = build_app()
    async with client_for(app) as c:
        r = await c.patch("/api/v1/prompts/lists/ideas", json={}, headers=AUTH)
    assert r.status_code == 400


async def test_update_list_not_found():
    app = build_app(_store(update_list=False))
    async with client_for(app) as c:
        r = await c.patch(
            "/api/v1/prompts/lists/ideas",
            json={"is_active": False},
            headers=AUTH,
        )
    assert r.status_code == 404


async def test_delete_list_ok():
    app = build_app(_store(delete_list=True))
    async with client_for(app) as c:
        r = await c.delete("/api/v1/prompts/lists/ideas", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True}


async def test_delete_list_not_found():
    app = build_app(_store(delete_list=False))
    async with client_for(app) as c:
        r = await c.delete("/api/v1/prompts/lists/ideas", headers=AUTH)
    assert r.status_code == 404


# ==================== PIPELINE CONTROL ====================


async def test_pipeline_status_without_components():
    # No prompt_agent / prompt_executor set on state -> getattr returns None.
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/pipeline/status", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["agent"]["running"] is False
    assert body["agent"]["last_scan"] is None
    assert body["executor"]["running"] is False


async def test_pipeline_status_with_components():
    agent = MagicMock(
        running=True,
        last_scan=datetime(2026, 7, 12, tzinfo=timezone.utc),
        last_pending_count=3,
        interval=60,
    )
    executor = MagicMock(
        running=True, active_count=1, completed_today=5, failed_today=2
    )
    app = build_app(agent=agent, executor=executor)
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/pipeline/status", headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["agent"]["running"] is True
    assert body["agent"]["last_scan"].startswith("2026-07-12")
    assert body["agent"]["pending_count"] == 3
    assert body["executor"]["completed_today"] == 5
    # Contrato PipelineStatus del panel (frontend/src/types/api.ts): el endpoint
    # REMAPEA nombres de atributo -> claves de salida (agent.interval ->
    # "interval_seconds", agent.last_pending_count -> "pending_count"). Blindamos
    # el set exacto de claves anidadas + los 3 campos que el mock preparaba pero
    # el test no asertaba, para que un rename/drop rompa aquí y no en el panel.
    assert body["agent"].keys() == {
        "running", "last_scan", "pending_count", "interval_seconds"
    }
    assert body["executor"].keys() == {
        "running", "active_count", "completed_today", "failed_today"
    }
    assert body["agent"]["interval_seconds"] == 60  # remapeo interval -> interval_seconds
    assert body["executor"]["active_count"] == 1
    assert body["executor"]["failed_today"] == 2


async def test_pipeline_pause_with_components():
    agent = MagicMock(stop=AsyncMock())
    executor = MagicMock(stop=AsyncMock())
    app = build_app(agent=agent, executor=executor)
    async with client_for(app) as c:
        r = await c.post("/api/v1/prompts/pipeline/pause", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "paused"}
    agent.stop.assert_awaited_once()
    executor.stop.assert_awaited_once()


async def test_pipeline_pause_without_components():
    app = build_app()
    async with client_for(app) as c:
        r = await c.post("/api/v1/prompts/pipeline/pause", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "paused"}


async def test_pipeline_resume_with_components():
    agent = MagicMock(start=AsyncMock())
    executor = MagicMock(start=AsyncMock())
    app = build_app(agent=agent, executor=executor)
    async with client_for(app) as c:
        r = await c.post("/api/v1/prompts/pipeline/resume", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "running"}
    agent.start.assert_awaited_once()
    executor.start.assert_awaited_once()


async def test_pipeline_resume_without_components():
    app = build_app()
    async with client_for(app) as c:
        r = await c.post("/api/v1/prompts/pipeline/resume", headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"success": True, "status": "running"}


# ==================== DEGRADED (store unavailable) & AUTH ====================


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/prompts/stats"),
        ("get", "/api/v1/prompts"),
        ("post", "/api/v1/prompts/notes"),
        ("get", "/api/v1/prompts/inbox"),
        ("get", "/api/v1/prompts/lists"),
    ],
)
async def test_store_unavailable_returns_503(method, path):
    app = build_app(store=None)
    async with client_for(app) as c:
        kwargs = {"headers": AUTH}
        if method == "post":
            kwargs["json"] = {"text": "x"}
        r = await getattr(c, method)(path, **kwargs)
    assert r.status_code == 503


async def test_requires_auth():
    app = build_app()
    async with client_for(app) as c:
        r = await c.get("/api/v1/prompts/stats")
    assert r.status_code == 401


async def test_invalid_api_key_401():
    app = build_app()
    async with client_for(app) as c:
        r = await c.get(
            "/api/v1/prompts/stats", headers={"X-API-Key": "bogus-key"}
        )
    assert r.status_code == 401


# ==================== STORE UNAVAILABLE (503) ====================
#
# Every endpoint guards on `request.app.state.prompt_store`; when it is None the
# handler raises HTTPException(503, "Prompt system not available") before any
# store call. Bodies below are the minimal valid payload so request validation
# passes and execution reaches that guard (covers the previously-uncovered 503
# branch on each endpoint).

_PID = "11111111-1111-1111-1111-111111111111"

_UNAVAILABLE_CASES = [
    ("post", "/api/v1/prompts", {"content": "x"}),
    ("get", "/api/v1/prompts/staging", None),
    ("get", "/api/v1/prompts/archive", None),
    ("get", f"/api/v1/prompts/{_PID}", None),
    ("patch", f"/api/v1/prompts/{_PID}", {"content": "x"}),
    ("delete", f"/api/v1/prompts/{_PID}", None),
    ("post", f"/api/v1/prompts/{_PID}/retry", None),
    ("post", f"/api/v1/prompts/{_PID}/classify", {"category": "work"}),
    ("post", f"/api/v1/prompts/{_PID}/stage", None),
    ("post", f"/api/v1/prompts/{_PID}/approve", None),
    ("post", f"/api/v1/prompts/{_PID}/archive", None),
    ("post", f"/api/v1/prompts/{_PID}/promote/list", {"list_slug": "s"}),
    ("post", f"/api/v1/prompts/{_PID}/promote/skill", {"name": "n", "trigger_pattern": "t"}),
    ("post", f"/api/v1/prompts/{_PID}/promote/mcp", None),
    ("post", "/api/v1/prompts/lists", {"name": "n"}),
    ("get", "/api/v1/prompts/lists/some-slug", None),
    ("patch", "/api/v1/prompts/lists/some-slug", {"description": "d"}),
    ("delete", "/api/v1/prompts/lists/some-slug", None),
]


@pytest.mark.parametrize("method,path,body", _UNAVAILABLE_CASES)
async def test_endpoint_returns_503_when_store_unavailable(method, path, body):
    app = build_app(store=None)
    async with client_for(app) as c:
        kwargs = {"headers": AUTH}
        if body is not None:
            kwargs["json"] = body
        r = await getattr(c, method)(path, **kwargs)
    assert r.status_code == 503
    assert r.json()["detail"] == "Prompt system not available"
