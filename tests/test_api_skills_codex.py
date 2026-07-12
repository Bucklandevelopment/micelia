"""
Tests for the Skills API router (app/api/v1/skills.py).

The router delegates to SkillsManager (already covered by its own service
tests), so here we drive the HTTP contract over a fresh FastAPI app with an
``AsyncMock`` manager injected on ``app.state.skills_manager``. The
``_get_manager`` fallback branches (missing prompt_store, singleton init,
RuntimeError) are driven through ``GET /skills/{slug}`` with
``get_skills_manager`` monkeypatched — the real singleton is never touched.

Former quirk (fixed in Ciclo 19): ``list_skills``/``create_skill`` now carry an
``except HTTPException: raise`` clause like every sibling endpoint, so the 503
from ``_get_manager`` (store not initialized) surfaces as a 503 on those routes
instead of being swallowed into a 500.
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import skills
from app.core.security import api_key_manager

# A dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-skills", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}

_UNSET = object()

CREATE_PAYLOAD = {
    "name": "Greet",
    "description": "Say hi",
    "trigger_pattern": "^hi",
    "prompt_template": "Say hi: {content}",
    "metadata": {"k": "v"},
}


def build_app(manager=_UNSET, prompt_store=_UNSET) -> FastAPI:
    """Build a FastAPI app with only the skills router and injected state."""
    app = FastAPI()
    app.include_router(skills.router, prefix="/api/v1")
    if manager is not _UNSET:
        app.state.skills_manager = manager
    if prompt_store is not _UNSET:
        app.state.prompt_store = prompt_store
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def fake_manager(**overrides) -> AsyncMock:
    """Fake SkillsManager with explicit (real dict/list/bool) return values."""
    m = AsyncMock()
    m.create_skill.return_value = {"slug": "greet", "name": "Greet", "is_active": True}
    m.list_skills.return_value = [
        {"slug": "a", "is_active": True},
        {"slug": "b", "is_active": False},
    ]
    m.get_skill.return_value = {"slug": "greet", "prompt_template": "Say hi: {content}"}
    m.update_skill.return_value = {"slug": "greet", "description": "new"}
    m.delete_skill.return_value = True
    m.toggle_skill.return_value = True
    m.test_skill.return_value = "Say hi: hola"
    for name, value in overrides.items():
        setattr(m, name, value)
    return m


# ==================== POST /skills ====================


async def test_create_skill_ok():
    manager = fake_manager()
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post("/api/v1/skills", json=CREATE_PAYLOAD, headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["slug"] == "greet"
    manager.create_skill.assert_awaited_once_with(
        name="Greet",
        description="Say hi",
        trigger_pattern="^hi",
        prompt_template="Say hi: {content}",
        metadata={"k": "v"},
    )


async def test_create_skill_value_error_400():
    manager = fake_manager(
        create_skill=AsyncMock(side_effect=ValueError("bad regex"))
    )
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post("/api/v1/skills", json=CREATE_PAYLOAD, headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad regex"


async def test_create_skill_generic_500():
    manager = fake_manager(create_skill=AsyncMock(side_effect=RuntimeError("boom")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post("/api/v1/skills", json=CREATE_PAYLOAD, headers=AUTH)
    assert resp.status_code == 500
    assert "Failed to create skill" in resp.json()["detail"]


async def test_create_skill_validation_422():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.post("/api/v1/skills", json={"name": "solo"}, headers=AUTH)
    assert resp.status_code == 422


# ==================== GET /skills ====================


async def test_list_skills_ok():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.get("/api/v1/skills", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["active"] == 1
    assert [s["slug"] for s in body["skills"]] == ["a", "b"]


async def test_list_skills_error_500():
    manager = fake_manager(list_skills=AsyncMock(side_effect=RuntimeError("db")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.get("/api/v1/skills", headers=AUTH)
    assert resp.status_code == 500


# ==================== GET /skills/{slug} ====================


async def test_get_skill_ok():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.get("/api/v1/skills/greet", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["slug"] == "greet"


async def test_get_skill_not_found_404():
    manager = fake_manager(get_skill=AsyncMock(return_value=None))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.get("/api/v1/skills/ghost", headers=AUTH)
    assert resp.status_code == 404
    assert "ghost" in resp.json()["detail"]


async def test_get_skill_error_500():
    manager = fake_manager(get_skill=AsyncMock(side_effect=RuntimeError("db")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.get("/api/v1/skills/greet", headers=AUTH)
    assert resp.status_code == 500


# ==================== PATCH /skills/{slug} ====================


async def test_update_skill_ok():
    manager = fake_manager()
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.patch(
            "/api/v1/skills/greet", json={"description": "new"}, headers=AUTH
        )
    assert resp.status_code == 200
    assert resp.json()["description"] == "new"
    # exclude_none: only the provided field reaches the manager
    manager.update_skill.assert_awaited_once_with("greet", {"description": "new"})


async def test_update_skill_empty_body_400():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.patch("/api/v1/skills/greet", json={}, headers=AUTH)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "No fields to update"


async def test_update_skill_not_found_404():
    manager = fake_manager(update_skill=AsyncMock(return_value=None))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.patch(
            "/api/v1/skills/ghost", json={"description": "new"}, headers=AUTH
        )
    assert resp.status_code == 404


async def test_update_skill_value_error_400():
    manager = fake_manager(update_skill=AsyncMock(side_effect=ValueError("bad")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.patch(
            "/api/v1/skills/greet", json={"description": "new"}, headers=AUTH
        )
    assert resp.status_code == 400


async def test_update_skill_generic_500():
    manager = fake_manager(update_skill=AsyncMock(side_effect=RuntimeError("db")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.patch(
            "/api/v1/skills/greet", json={"description": "new"}, headers=AUTH
        )
    assert resp.status_code == 500


# ==================== DELETE /skills/{slug} ====================


async def test_delete_skill_ok():
    manager = fake_manager()
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.delete("/api/v1/skills/greet", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["slug"] == "greet"
    manager.delete_skill.assert_awaited_once_with("greet")


async def test_delete_skill_not_found_404():
    manager = fake_manager(delete_skill=AsyncMock(return_value=False))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.delete("/api/v1/skills/ghost", headers=AUTH)
    assert resp.status_code == 404


async def test_delete_skill_error_500():
    manager = fake_manager(delete_skill=AsyncMock(side_effect=RuntimeError("db")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.delete("/api/v1/skills/greet", headers=AUTH)
    assert resp.status_code == 500


# ==================== POST /skills/{slug}/toggle ====================


async def test_toggle_skill_activated():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.post("/api/v1/skills/greet/toggle", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is True
    assert "activated" in body["message"]


async def test_toggle_skill_deactivated():
    # False is a valid new state: the router must distinguish it from None.
    manager = fake_manager(toggle_skill=AsyncMock(return_value=False))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post("/api/v1/skills/greet/toggle", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert "deactivated" in body["message"]


async def test_toggle_skill_not_found_404():
    manager = fake_manager(toggle_skill=AsyncMock(return_value=None))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post("/api/v1/skills/ghost/toggle", headers=AUTH)
    assert resp.status_code == 404


async def test_toggle_skill_error_500():
    manager = fake_manager(toggle_skill=AsyncMock(side_effect=RuntimeError("db")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post("/api/v1/skills/greet/toggle", headers=AUTH)
    assert resp.status_code == 500


# ==================== POST /skills/{slug}/test ====================


async def test_test_skill_ok():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.post(
            "/api/v1/skills/greet/test", json={"prompt": "hola"}, headers=AUTH
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["skill"] == "greet"
    assert body["original_prompt"] == "hola"
    assert body["transformed_prompt"] == "Say hi: hola"
    assert body["template_used"] == "Say hi: {content}"


async def test_test_skill_not_found_404():
    manager = fake_manager(test_skill=AsyncMock(return_value=None))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post(
            "/api/v1/skills/ghost/test", json={"prompt": "hola"}, headers=AUTH
        )
    assert resp.status_code == 404


async def test_test_skill_no_template_used():
    # test_skill succeeds but get_skill returns None -> template_used == "".
    manager = fake_manager(get_skill=AsyncMock(return_value=None))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post(
            "/api/v1/skills/greet/test", json={"prompt": "hola"}, headers=AUTH
        )
    assert resp.status_code == 200
    assert resp.json()["template_used"] == ""


async def test_test_skill_error_500():
    manager = fake_manager(test_skill=AsyncMock(side_effect=RuntimeError("db")))
    async with client_for(build_app(manager=manager)) as ac:
        resp = await ac.post(
            "/api/v1/skills/greet/test", json={"prompt": "hola"}, headers=AUTH
        )
    assert resp.status_code == 500


async def test_test_skill_validation_422():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.post(
            "/api/v1/skills/greet/test", json={"prompt": ""}, headers=AUTH
        )
    assert resp.status_code == 422


# ==================== _get_manager fallbacks ====================


async def test_manager_missing_store_503():
    # Neither skills_manager nor prompt_store on app.state.
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/skills/greet", headers=AUTH)
    assert resp.status_code == 503
    assert "prompt_store not initialized" in resp.json()["detail"]


async def test_manager_fallback_singleton_caches(monkeypatch):
    fake = fake_manager()
    monkeypatch.setattr(skills, "get_skills_manager", lambda store: fake)
    app = build_app(prompt_store=MagicMock())
    async with client_for(app) as ac:
        resp = await ac.get("/api/v1/skills/greet", headers=AUTH)
    assert resp.status_code == 200
    # The resolved singleton is cached on app.state for future requests.
    assert app.state.skills_manager is fake


async def test_manager_fallback_runtime_error_503(monkeypatch):
    def boom(store):
        raise RuntimeError("skills manager not ready")

    monkeypatch.setattr(skills, "get_skills_manager", boom)
    async with client_for(build_app(prompt_store=MagicMock())) as ac:
        resp = await ac.get("/api/v1/skills/greet", headers=AUTH)
    assert resp.status_code == 503
    assert "not ready" in resp.json()["detail"]


async def test_list_skills_missing_store_503():
    # Fixed in Ciclo 19: list_skills now re-raises HTTPException, so the 503
    # from _get_manager surfaces intact instead of becoming a 500.
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/skills", headers=AUTH)
    assert resp.status_code == 503
    assert "prompt_store not initialized" in resp.json()["detail"]


async def test_create_skill_missing_store_503():
    # Fixed in Ciclo 19: create_skill re-raises the 503 from _get_manager
    # (store not initialized) instead of swallowing it into a 500.
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/skills", json=CREATE_PAYLOAD, headers=AUTH)
    assert resp.status_code == 503
    assert "prompt_store not initialized" in resp.json()["detail"]


# ==================== auth ====================


async def test_requires_auth():
    async with client_for(build_app(manager=fake_manager())) as ac:
        resp = await ac.get("/api/v1/skills")
    assert resp.status_code in (401, 403)
