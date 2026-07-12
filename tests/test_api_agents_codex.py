"""
Tests for the Multi-Agent Orchestration API router (app/api/v1/agents.py).

The six endpoints read their collaborators from ``request.app.state``
(``crew_manager`` and ``workflow_engine``) plus the static ``WORKFLOWS``
registry. We drive the HTTP contract over a fresh ``FastAPI()`` with only this
router mounted, injecting ``AsyncMock``/``MagicMock`` collaborators into
``app.state`` — no infra, no network, no lifespan.

Awaited collaborator methods (``crew_manager.execute``) are ``AsyncMock``; the
synchronous ones (``list_crews``, ``create_crew``, ``get_runs``, ``get_run``)
are plain ``MagicMock`` returns. The two ``_get_*`` helpers raise 503 when their
state attribute is missing — exercised by the "missing dependency" tests.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import agents
from app.core.security import api_key_manager
from app.services.agents.workflows import WORKFLOWS

# Dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-agents", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app() -> FastAPI:
    """Build a FastAPI app with only the agents router mounted."""
    app = FastAPI()
    app.include_router(agents.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def configure_state(app: FastAPI, **attrs) -> None:
    """Set the given ``app.state`` attributes (helpers read them via getattr)."""
    for name, value in attrs.items():
        setattr(app.state, name, value)


# ---------------------------------------------------------------- fakes


def fake_crew_manager(**overrides) -> MagicMock:
    """CrewManager with sensible defaults; ``execute`` is awaited (AsyncMock)."""
    mgr = MagicMock()
    mgr.list_crews.return_value = [
        {"id": "c1", "name": "Alpha", "workflow": "reviewed_execute"},
        {"id": "c2", "name": "Beta", "workflow": "simple_execute"},
    ]
    mgr.create_crew.return_value = {
        "id": "c3",
        "name": "Gamma",
        "agents": ["planner", "executor"],
        "workflow": "simple_execute",
    }
    mgr.execute = AsyncMock(
        return_value={"status": "completed", "run_id": "r1", "output": "ok"}
    )
    for name, value in overrides.items():
        setattr(mgr, name, value)
    return mgr


def fake_workflow_engine(**overrides) -> MagicMock:
    """WorkflowEngine whose ``get_runs``/``get_run`` are synchronous."""
    engine = MagicMock()
    engine.get_runs.return_value = [
        {
            "run_id": "r1",
            "prompt_id": "p1",
            "workflow": "reviewed_execute",
            "status": "completed",
            "total_duration_ms": 1200,
            "total_cost_usd": 0.01,
            "steps": [{"agent": "planner"}, {"agent": "executor"}],
            "started_at": "2026-07-12T00:00:00Z",
            "completed_at": "2026-07-12T00:00:02Z",
        }
    ]
    engine.get_run.return_value = {
        "run_id": "r1",
        "status": "completed",
        "steps": [{"agent": "planner"}],
    }
    for name, value in overrides.items():
        setattr(engine, name, value)
    return engine


# ---------------------------------------------------------------- crews


async def test_list_crews_happy():
    app = build_app()
    configure_state(app, crew_manager=fake_crew_manager())
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/agents/crews", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert [c["id"] for c in body["crews"]] == ["c1", "c2"]


async def test_list_crews_no_manager_503():
    # No crew_manager on state → _get_crew_manager raises 503.
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/agents/crews", headers=AUTH)
    assert resp.status_code == 503
    assert "not available" in resp.json()["detail"]


async def test_create_crew_happy():
    app = build_app()
    mgr = fake_crew_manager()
    configure_state(app, crew_manager=mgr)
    payload = {
        "name": "Gamma",
        "agents": ["planner", "executor"],
        "workflow": "simple_execute",
    }
    async with client_for(app) as ac:
        resp = await ac.post("/api/v1/agents/crews", json=payload, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["id"] == "c3"
    mgr.create_crew.assert_called_once_with(
        name="Gamma", agents=["planner", "executor"], workflow="simple_execute"
    )


async def test_create_crew_value_error_400():
    app = build_app()
    mgr = fake_crew_manager(
        create_crew=MagicMock(side_effect=ValueError("unknown workflow"))
    )
    configure_state(app, crew_manager=mgr)
    payload = {"name": "Bad", "agents": ["planner"], "workflow": "nope"}
    async with client_for(app) as ac:
        resp = await ac.post("/api/v1/agents/crews", json=payload, headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "unknown workflow"


async def test_create_crew_validation_422():
    # Empty agents list violates CrewCreate(min_length=1) → 422 before the router
    # body runs; no crew_manager needed.
    app = build_app()
    configure_state(app, crew_manager=fake_crew_manager())
    payload = {"name": "X", "agents": [], "workflow": "simple_execute"}
    async with client_for(app) as ac:
        resp = await ac.post("/api/v1/agents/crews", json=payload, headers=AUTH)
    assert resp.status_code == 422


# ---------------------------------------------------------------- workflows


async def test_list_workflows_matches_registry():
    # No app.state deps: reads the real WORKFLOWS registry.
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/agents/workflows", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(WORKFLOWS)
    names = {wf["name"] for wf in body["workflows"]}
    assert names == set(WORKFLOWS.keys())

    by_name = {wf["name"]: wf for wf in body["workflows"]}
    reviewed = by_name["reviewed_execute"]
    src = WORKFLOWS["reviewed_execute"]
    assert reviewed["display_name"] == src.name
    assert reviewed["description"] == src.description
    assert reviewed["max_retries"] == src.max_retries
    assert len(reviewed["steps"]) == len(src.steps)
    assert reviewed["steps"][0] == {
        "agent": "planner",
        "action": "analyze_and_plan",
        "next_on_success": "execute",
        "next_on_failure": None,
    }
    # agents_used is the de-duplicated set of step agents.
    assert set(reviewed["agents_used"]) == {s.agent for s in src.steps}


# ---------------------------------------------------------------- execute


async def test_execute_happy():
    app = build_app()
    mgr = fake_crew_manager()
    configure_state(app, crew_manager=mgr)
    payload = {"prompt_id": "p1", "workflow": "simple_execute"}
    async with client_for(app) as ac:
        resp = await ac.post("/api/v1/agents/execute", json=payload, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    mgr.execute.assert_awaited_once_with(
        prompt_id="p1", crew_id=None, workflow="simple_execute"
    )


async def test_execute_failed_branch():
    # status == "failed" exercises the log.warning branch; body still passes through.
    app = build_app()
    mgr = fake_crew_manager(
        execute=AsyncMock(
            return_value={"status": "failed", "error": "executor exploded"}
        )
    )
    configure_state(app, crew_manager=mgr)
    payload = {"prompt_id": "p9", "crew_id": "c1"}
    async with client_for(app) as ac:
        resp = await ac.post("/api/v1/agents/execute", json=payload, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"status": "failed", "error": "executor exploded"}
    mgr.execute.assert_awaited_once_with(
        prompt_id="p9", crew_id="c1", workflow=None
    )


async def test_execute_no_manager_503():
    payload = {"prompt_id": "p1"}
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/agents/execute", json=payload, headers=AUTH)
    assert resp.status_code == 503


# ---------------------------------------------------------------- runs


async def test_list_runs_happy_projection():
    app = build_app()
    configure_state(app, workflow_engine=fake_workflow_engine())
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/agents/runs", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    run = body["runs"][0]
    assert run == {
        "run_id": "r1",
        "prompt_id": "p1",
        "workflow": "reviewed_execute",
        "status": "completed",
        "total_duration_ms": 1200,
        "total_cost_usd": 0.01,
        "step_count": 2,  # len(steps)
        "started_at": "2026-07-12T00:00:00Z",
        "completed_at": "2026-07-12T00:00:02Z",
    }


async def test_list_runs_query_params_echoed():
    app = build_app()
    engine = fake_workflow_engine(get_runs=MagicMock(return_value=[]))
    configure_state(app, workflow_engine=engine)
    async with client_for(app) as ac:
        resp = await ac.get(
            "/api/v1/agents/runs?limit=200&offset=10", headers=AUTH
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"runs": [], "count": 0, "limit": 200, "offset": 10}
    engine.get_runs.assert_called_once_with(limit=200, offset=10)


async def test_list_runs_limit_out_of_bounds_422():
    # limit le=200 → 201 rejected by the Query validator before the body runs.
    app = build_app()
    configure_state(app, workflow_engine=fake_workflow_engine())
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/agents/runs?limit=201", headers=AUTH)
    assert resp.status_code == 422


async def test_list_runs_no_engine_503():
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/agents/runs", headers=AUTH)
    assert resp.status_code == 503
    assert "engine not available" in resp.json()["detail"]


async def test_get_run_happy():
    app = build_app()
    configure_state(app, workflow_engine=fake_workflow_engine())
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/agents/runs/r1", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["run_id"] == "r1"


async def test_get_run_not_found_404():
    app = build_app()
    engine = fake_workflow_engine(get_run=MagicMock(return_value=None))
    configure_state(app, workflow_engine=engine)
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/agents/runs/missing", headers=AUTH)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Run not found."


# ---------------------------------------------------------------- auth


async def test_requires_auth():
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/agents/crews")
    assert resp.status_code in (401, 403)
