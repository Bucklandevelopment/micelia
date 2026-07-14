"""
Tests for the MCP generator API router (app/api/v1/mcp.py).

The router delegates all generation/lifecycle work to the MCPGenerator
singleton (already covered by its own service tests), so here we drive the
HTTP contract over a fresh FastAPI app with ``get_mcp_generator`` monkeypatched
to a synchronous MagicMock — the real singleton is never constructed and no
filesystem is touched. The pure heuristic ``_parse_prompt_to_spec`` is
exercised directly.
"""

import contextlib
from unittest.mock import MagicMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import mcp
from app.core.security import api_key_manager

# A dedicated valid API key for this module (verify_auth uses the shared manager).
TEST_API_KEY = api_key_manager.generate_key(
    name="test-mcp", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}

GENERATE_PAYLOAD = {
    "name": "weather-server",
    "description": "Weather tools",
    "tools": [{"name": "fetch"}],
    "language": "python",
}

# Payload EXACTO que envia MCPGenerateForm (frontend/src/app/skills/page.tsx) cuando
# el usuario deja la descripcion en blanco: el <input> de description NO es `required`
# y handleSubmit solo exige name + al menos un tool con nombre. Antes daba 422
# (string_too_short) porque GenerateRequest.description usaba min_length=1. Espejo del
# guard PANEL_CREATE_SKILL_NO_DESCRIPTION de C60.
PANEL_GENERATE_NO_DESCRIPTION = {
    "name": "my-mcp-server",
    "description": "",
    "tools": [{"name": "fetch", "description": ""}],
    "language": "python",
}


def build_app() -> FastAPI:
    """Build a FastAPI app with only the MCP router mounted."""
    app = FastAPI()
    app.include_router(mcp.router, prefix="/api/v1")
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def fake_generator(**overrides) -> MagicMock:
    """Fake MCPGenerator: all methods synchronous, explicit return values."""
    g = MagicMock()
    g.generate.return_value = {"server_id": "srv-1", "path": "/tmp/srv-1"}
    g.list_servers.return_value = [{"server_id": "srv-1"}]
    g.get_server.return_value = {"server_id": "srv-1", "code": "print('hi')"}
    g.delete_server.return_value = None
    g.start_server.return_value = {"server_id": "srv-1", "status": "running"}
    g.stop_server.return_value = {"server_id": "srv-1", "status": "stopped"}
    for name, value in overrides.items():
        setattr(g, name, value)
    return g


def patch_generator(monkeypatch, generator: MagicMock) -> None:
    monkeypatch.setattr(mcp, "get_mcp_generator", lambda: generator)


# ==================== _parse_prompt_to_spec ====================


def test_parse_prompt_named_server():
    # Prompt must not start with create/build/make: the regex matches leftmost.
    spec = mcp._parse_prompt_to_spec(
        "A server called weather that can fetch data"
    )
    assert spec["name"] == "weather"


def test_parse_prompt_name_from_first_words():
    spec = mcp._parse_prompt_to_spec("weather info service for daily use")
    assert spec["name"] == "weather-info-service"


def test_parse_prompt_name_fallback():
    spec = mcp._parse_prompt_to_spec("1234 5678 90!!")
    assert spec["name"] == "mcp-server"


def test_parse_prompt_bullet_tools():
    spec = mcp._parse_prompt_to_spec("- fetch data\n- store files")
    names = [t["name"] for t in spec["tools"]]
    assert names == ["fetch_data", "store_files"]
    for tool in spec["tools"]:
        assert tool["parameters"] == [
            {"name": "input", "type": "string", "description": "Input data"}
        ]


def test_parse_prompt_default_tool():
    spec = mcp._parse_prompt_to_spec("nothing")
    assert len(spec["tools"]) == 1
    tool = spec["tools"][0]
    assert tool["name"] == "process"
    assert tool["description"].startswith("Process request for:")


def test_parse_prompt_short_tokens_filtered():
    # The bullet yields a <=2 char tool name, which is skipped -> default tool.
    spec = mcp._parse_prompt_to_spec("- ab")
    assert [t["name"] for t in spec["tools"]] == ["process"]


def test_parse_prompt_caps_ten_tools():
    words = [
        "alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
        "golf", "hotel", "india", "juliet", "kilo", "lima",
    ]
    prompt = "\n".join(f"- {w} data" for w in words)
    spec = mcp._parse_prompt_to_spec(prompt)
    assert len(spec["tools"]) == 10


def test_parse_prompt_description_truncated():
    prompt = "word " * 60  # 300 chars
    spec = mcp._parse_prompt_to_spec(prompt)
    assert len(spec["description"]) <= 200


# ==================== POST /mcp/generate ====================


async def test_generate_ok(monkeypatch):
    gen = fake_generator()
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/generate", json=GENERATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 200
    assert resp.json() == {"server_id": "srv-1", "path": "/tmp/srv-1"}
    gen.generate.assert_called_once_with(
        name="weather-server",
        description="Weather tools",
        tools=[{"name": "fetch", "description": "", "parameters": []}],
        language="python",
    )


async def test_generate_accepts_panel_empty_description(monkeypatch):
    """El form del panel puede enviar description="" (input no `required`).

    Antes daba 422 (min_length=1); ahora debe dar 200 y propagar "" al generador
    sin coercion. Mutacion: restaurar Field(..., min_length=1) vuelve a 422 y este
    test falla nombrando el payload del panel.
    """
    gen = fake_generator()
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/generate", json=PANEL_GENERATE_NO_DESCRIPTION, headers=AUTH
        )
    assert resp.status_code == 200
    assert resp.json() == {"server_id": "srv-1", "path": "/tmp/srv-1"}
    assert gen.generate.call_args.kwargs["description"] == ""


async def test_generate_value_error_400(monkeypatch):
    gen = fake_generator(generate=MagicMock(side_effect=ValueError("bad spec")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/generate", json=GENERATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "bad spec"


async def test_generate_exists_409(monkeypatch):
    gen = fake_generator(generate=MagicMock(side_effect=FileExistsError("dup")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/generate", json=GENERATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 409


async def test_generate_generic_500(monkeypatch):
    gen = fake_generator(generate=MagicMock(side_effect=RuntimeError("boom")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/generate", json=GENERATE_PAYLOAD, headers=AUTH
        )
    assert resp.status_code == 500
    assert "Generation failed" in resp.json()["detail"]


async def test_generate_validation_422(monkeypatch):
    patch_generator(monkeypatch, fake_generator())
    async with client_for(build_app()) as ac:
        bad_name = await ac.post(
            "/api/v1/mcp/generate",
            json={**GENERATE_PAYLOAD, "name": "Bad Name!"},
            headers=AUTH,
        )
        empty_tools = await ac.post(
            "/api/v1/mcp/generate",
            json={**GENERATE_PAYLOAD, "tools": []},
            headers=AUTH,
        )
        bad_language = await ac.post(
            "/api/v1/mcp/generate",
            json={**GENERATE_PAYLOAD, "language": "rust"},
            headers=AUTH,
        )
    assert bad_name.status_code == 422
    assert empty_tools.status_code == 422
    assert bad_language.status_code == 422


# ==================== POST /mcp/from-prompt ====================


async def test_from_prompt_ok(monkeypatch):
    gen = fake_generator()
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/from-prompt",
            json={"prompt": "A server called weather that can fetch data"},
            headers=AUTH,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["parsed_from_prompt"] is True
    assert body["parsed_spec"]["name"] == "weather"
    assert len(body["parsed_spec"]["tools"]) >= 1
    assert gen.generate.call_args.kwargs["name"] == "weather"
    assert gen.generate.call_args.kwargs["language"] == "python"


async def test_from_prompt_value_error_400(monkeypatch):
    gen = fake_generator(generate=MagicMock(side_effect=ValueError("bad")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/from-prompt",
            json={"prompt": "A server called weather that can fetch data"},
            headers=AUTH,
        )
    assert resp.status_code == 400


async def test_from_prompt_generic_500(monkeypatch):
    gen = fake_generator(generate=MagicMock(side_effect=RuntimeError("boom")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/from-prompt",
            json={"prompt": "A server called weather that can fetch data"},
            headers=AUTH,
        )
    assert resp.status_code == 500
    assert "Generation failed" in resp.json()["detail"]


async def test_from_prompt_short_prompt_422(monkeypatch):
    patch_generator(monkeypatch, fake_generator())
    async with client_for(build_app()) as ac:
        resp = await ac.post(
            "/api/v1/mcp/from-prompt", json={"prompt": "short"}, headers=AUTH
        )
    assert resp.status_code == 422


# ==================== GET /mcp/servers ====================


async def test_list_servers_ok(monkeypatch):
    patch_generator(monkeypatch, fake_generator())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/mcp/servers", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"servers": [{"server_id": "srv-1"}], "count": 1}


async def test_list_servers_error_500(monkeypatch):
    gen = fake_generator(list_servers=MagicMock(side_effect=OSError("disk")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/mcp/servers", headers=AUTH)
    assert resp.status_code == 500
    assert resp.json()["detail"] == "disk"


# ==================== GET /mcp/servers/{server_id} ====================


async def test_get_server_ok(monkeypatch):
    patch_generator(monkeypatch, fake_generator())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/mcp/servers/srv-1", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["server_id"] == "srv-1"


async def test_get_server_not_found_404(monkeypatch):
    gen = fake_generator(get_server=MagicMock(side_effect=FileNotFoundError()))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/mcp/servers/ghost", headers=AUTH)
    assert resp.status_code == 404
    assert "ghost" in resp.json()["detail"]


async def test_get_server_error_500(monkeypatch):
    gen = fake_generator(get_server=MagicMock(side_effect=OSError("disk")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/mcp/servers/srv-1", headers=AUTH)
    assert resp.status_code == 500


# ==================== DELETE /mcp/servers/{server_id} ====================


async def test_delete_server_ok(monkeypatch):
    gen = fake_generator()
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.delete("/api/v1/mcp/servers/srv-1", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["server_id"] == "srv-1"
    gen.delete_server.assert_called_once_with("srv-1")


async def test_delete_server_not_found_404(monkeypatch):
    gen = fake_generator(delete_server=MagicMock(side_effect=FileNotFoundError()))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.delete("/api/v1/mcp/servers/ghost", headers=AUTH)
    assert resp.status_code == 404


async def test_delete_server_running_409(monkeypatch):
    gen = fake_generator(delete_server=MagicMock(side_effect=RuntimeError("running")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.delete("/api/v1/mcp/servers/srv-1", headers=AUTH)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "running"


async def test_delete_server_error_500(monkeypatch):
    gen = fake_generator(delete_server=MagicMock(side_effect=OSError("disk")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.delete("/api/v1/mcp/servers/srv-1", headers=AUTH)
    assert resp.status_code == 500


# ==================== POST /mcp/servers/{server_id}/start ====================


async def test_start_server_ok(monkeypatch):
    patch_generator(monkeypatch, fake_generator())
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/mcp/servers/srv-1/start", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


async def test_start_server_not_found_404(monkeypatch):
    gen = fake_generator(start_server=MagicMock(side_effect=FileNotFoundError()))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/mcp/servers/ghost/start", headers=AUTH)
    assert resp.status_code == 404


async def test_start_server_conflict_409(monkeypatch):
    gen = fake_generator(start_server=MagicMock(side_effect=RuntimeError("already")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/mcp/servers/srv-1/start", headers=AUTH)
    assert resp.status_code == 409


async def test_start_server_error_500(monkeypatch):
    gen = fake_generator(start_server=MagicMock(side_effect=OSError("spawn")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/mcp/servers/srv-1/start", headers=AUTH)
    assert resp.status_code == 500


# ==================== POST /mcp/servers/{server_id}/stop ====================


async def test_stop_server_ok(monkeypatch):
    patch_generator(monkeypatch, fake_generator())
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/mcp/servers/srv-1/stop", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"


async def test_stop_server_conflict_409(monkeypatch):
    gen = fake_generator(stop_server=MagicMock(side_effect=RuntimeError("not running")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/mcp/servers/srv-1/stop", headers=AUTH)
    assert resp.status_code == 409


async def test_stop_server_error_500(monkeypatch):
    gen = fake_generator(stop_server=MagicMock(side_effect=OSError("kill")))
    patch_generator(monkeypatch, gen)
    async with client_for(build_app()) as ac:
        resp = await ac.post("/api/v1/mcp/servers/srv-1/stop", headers=AUTH)
    assert resp.status_code == 500


# ==================== GET /mcp/templates ====================


async def test_templates_ok(monkeypatch):
    patch_generator(monkeypatch, fake_generator())
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/mcp/templates", headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert {t["language"] for t in body["templates"]} == {"python", "typescript"}


# ==================== auth ====================


async def test_requires_auth():
    async with client_for(build_app()) as ac:
        resp = await ac.get("/api/v1/mcp/templates")
    assert resp.status_code in (401, 403)
