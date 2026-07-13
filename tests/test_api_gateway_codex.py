"""
Tests for the API Gateway router (app/api/v1/gateway.py).

Two surfaces:

1. ``proxy_request`` (reached via the 4 ``api_route`` proxies
   ``/gateway/{health,research,education,security}/{path}``): forwards to the
   upstream ``request.app.state.http_client`` and reproduces status/headers/body.
   Covers header filtering (``host``/``content-length`` dropped), body only on
   POST/PUT/PATCH, query params, the unknown-service 404, and the httpx error
   translations (Timeout→504, ConnectError→503, generic→502).
2. ``research_to_course_pipeline`` (``POST /gateway/pipeline/research-to-course``):
   papers → synthesis → course chain over ``client.get``/``client.post``, with the
   ``education_service_enabled`` branch, the ``event_store`` append, and the
   exception→500 path.

Everything is in-process: ``http_client`` and ``event_store`` are mocks in
``app.state``; no network, infra or subprocess. ``SERVICE_ROUTES`` is a
module-level constant, so the 404 branch is exercised by monkeypatching it.
"""

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import gateway
from app.core.security import api_key_manager

TEST_API_KEY = api_key_manager.generate_key(
    name="test-gateway", permissions={"all"}, rate_limit=100000
)
AUTH = {"X-API-Key": TEST_API_KEY}


def build_app(http_client=None, event_store=None) -> FastAPI:
    """Mount only the gateway router; seed the state it reads directly."""
    app = FastAPI()
    app.include_router(gateway.router, prefix="/api/v1")
    app.state.http_client = http_client if http_client is not None else AsyncMock()
    app.state.event_store = event_store
    return app


@contextlib.asynccontextmanager
async def client_for(app: FastAPI):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def upstream_response(
    *, status_code=200, content=b'{"ok": true}', content_type="application/json"
) -> SimpleNamespace:
    """A minimal stand-in for the upstream httpx.Response the router re-wraps."""
    return SimpleNamespace(
        status_code=status_code,
        content=content,
        headers={"content-type": content_type, "x-upstream": "1"},
    )


# ============================================================ proxy happy paths


async def test_proxy_get_reproduces_upstream_and_strips_headers():
    client = AsyncMock()
    client.request.return_value = upstream_response(content=b"HELLO")
    async with client_for(build_app(client)) as ac:
        resp = await ac.get(
            "/api/v1/gateway/health/api/status",
            params={"q": "1"},
            headers={**AUTH, "X-Custom": "keep"},
        )
    assert resp.status_code == 200
    assert resp.content == b"HELLO"
    assert resp.headers["x-upstream"] == "1"
    kwargs = client.request.call_args.kwargs
    assert kwargs["method"] == "GET"
    assert kwargs["url"].endswith("/api/status")
    assert kwargs["params"] == {"q": "1"}
    assert kwargs["content"] is None  # GET → no body
    # host + content-length filtered out; custom header preserved
    fwd = {k.lower(): v for k, v in kwargs["headers"].items()}
    assert "host" not in fwd
    assert "content-length" not in fwd
    assert fwd.get("x-custom") == "keep"


async def test_proxy_post_forwards_body():
    client = AsyncMock()
    client.request.return_value = upstream_response(status_code=201, content=b"{}")
    async with client_for(build_app(client)) as ac:
        resp = await ac.post(
            "/api/v1/gateway/research/papers",
            json={"query": "aging"},
            headers=AUTH,
        )
    assert resp.status_code == 201
    kwargs = client.request.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["content"] == b'{"query":"aging"}'  # httpx compact separators


@pytest.mark.parametrize(
    "prefix,expected_service_url_attr",
    [
        ("health", "health_service_url"),
        ("research", "research_service_url"),
        ("education", "education_service_url"),
        ("security", "security_service_url"),
    ],
)
async def test_all_four_proxies_route_to_their_service(
    prefix, expected_service_url_attr
):
    client = AsyncMock()
    client.request.return_value = upstream_response()
    async with client_for(build_app(client)) as ac:
        resp = await ac.get(f"/api/v1/gateway/{prefix}/ping", headers=AUTH)
    assert resp.status_code == 200
    base = getattr(gateway.settings, expected_service_url_attr)
    assert client.request.call_args.kwargs["url"] == f"{base}/ping"


# ============================================================ proxy error branches


async def test_proxy_unknown_service_404(monkeypatch):
    # Empty the route map so SERVICE_ROUTES.get("health") is None → 404.
    monkeypatch.setattr(gateway, "SERVICE_ROUTES", {})
    client = AsyncMock()
    async with client_for(build_app(client)) as ac:
        resp = await ac.get("/api/v1/gateway/health/x", headers=AUTH)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]
    client.request.assert_not_called()


@pytest.mark.parametrize(
    "exc,code",
    [
        (httpx.TimeoutException("t"), 504),
        (httpx.ConnectError("c"), 503),
        (RuntimeError("boom"), 502),
    ],
)
async def test_proxy_error_translations(exc, code):
    client = AsyncMock()
    client.request.side_effect = exc
    async with client_for(build_app(client)) as ac:
        resp = await ac.get("/api/v1/gateway/security/scan", headers=AUTH)
    assert resp.status_code == code


# ============================================================ pipeline


def _json_resp(payload) -> MagicMock:
    r = MagicMock()
    r.json.return_value = payload
    return r


async def test_pipeline_full_with_course_and_event(monkeypatch):
    monkeypatch.setattr(gateway.settings, "education_service_enabled", True)
    client = AsyncMock()
    # canela-molida devuelve una LISTA de papers (contrato real de
    # /api/papers/search/openalex -> list[dict]), no un envoltorio {"results"}.
    client.get.return_value = _json_resp([{"id": 1}, {"id": 2}])
    client.post.side_effect = [
        _json_resp({"answer": "A" * 30, "contexts": [1, 2, 3]}),  # synthesis
        _json_resp({"course_id": "c1"}),  # course
    ]
    store = AsyncMock()
    async with client_for(build_app(client, event_store=store)) as ac:
        resp = await ac.post(
            "/api/v1/gateway/pipeline/research-to-course",
            params={"topic": "longevity"},
            headers=AUTH,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["papers_analyzed"] == 2
    assert data["course"] == {"course_id": "c1"}
    assert data["synthesis"]["sources"] == 3
    store.append_event.assert_awaited_once()
    payload = store.append_event.call_args.kwargs["payload"]
    assert payload["papers_found"] == 2
    assert payload["course_created"] is True
    # Contrato con los dominios reales: `limit` (no `per_page`) en openalex y el
    # prefijo NestJS /api en el POST de creación de curso de ideacursi.
    assert client.get.call_args.kwargs["params"] == {"query": "longevity", "limit": 50}
    assert client.get.call_args.args[0].endswith("/api/papers/search/openalex")
    course_url = client.post.call_args_list[1].args[0]
    assert course_url.endswith("/api/courses/create")
    # El CUERPO debe respetar el CreateCourseDto real de ideacursi
    # (`{userId, idea, description, studentLevel}`), no el contrato ficticio
    # `{title, target_audience, num_modules, source_synthesis}`. En concreto
    # `userId` es obligatorio (ideacursi hace `userId.match(...)` → 500 si falta).
    course_body = client.post.call_args_list[1].kwargs["json"]
    assert course_body == {
        "userId": "micelia-pipeline",
        "idea": "longevity",
        "description": "A" * 30,
        "studentLevel": "intermediate",
    }


async def test_pipeline_education_disabled_no_course(monkeypatch):
    monkeypatch.setattr(gateway.settings, "education_service_enabled", False)
    client = AsyncMock()
    client.get.return_value = _json_resp([{"id": 1}])  # lista real de canela
    client.post.return_value = _json_resp({"answer": "short", "contexts": []})
    async with client_for(build_app(client, event_store=None)) as ac:
        resp = await ac.post(
            "/api/v1/gateway/pipeline/research-to-course",
            params={"topic": "sleep"},
            headers=AUTH,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["course"] is None
    assert data["papers_analyzed"] == 1
    # only the synthesis POST, no course POST
    assert client.post.await_count == 1


async def test_pipeline_no_event_store_skips_append(monkeypatch):
    monkeypatch.setattr(gateway.settings, "education_service_enabled", False)
    client = AsyncMock()
    client.get.return_value = _json_resp([])  # lista vacía real de canela
    client.post.return_value = _json_resp({"answer": "", "contexts": []})
    # event_store None → the `if event_store:` guard is False, no crash.
    async with client_for(build_app(client, event_store=None)) as ac:
        resp = await ac.post(
            "/api/v1/gateway/pipeline/research-to-course",
            params={"topic": "x"},
            headers=AUTH,
        )
    assert resp.status_code == 200
    assert resp.json()["papers_analyzed"] == 0


async def test_pipeline_upstream_error_500(monkeypatch):
    monkeypatch.setattr(gateway.settings, "education_service_enabled", True)
    client = AsyncMock()
    client.get.side_effect = RuntimeError("papers down")
    async with client_for(build_app(client, event_store=AsyncMock())) as ac:
        resp = await ac.post(
            "/api/v1/gateway/pipeline/research-to-course",
            params={"topic": "x"},
            headers=AUTH,
        )
    assert resp.status_code == 500
    assert "Pipeline failed" in resp.json()["detail"]


# ============================================================ auth


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/gateway/health/x"),
        ("post", "/api/v1/gateway/pipeline/research-to-course?topic=x"),
    ],
)
async def test_requires_auth(method, path):
    async with client_for(build_app()) as ac:
        resp = await getattr(ac, method)(path)
    assert resp.status_code in (401, 403)


async def test_invalid_key_rejected():
    async with client_for(build_app()) as ac:
        resp = await ac.get(
            "/api/v1/gateway/health/x", headers={"X-API-Key": "bogus"}
        )
    assert resp.status_code == 401
