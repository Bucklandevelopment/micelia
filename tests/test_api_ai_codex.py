"""
Tests for the AI/compute-router endpoints (app.api.v1.ai), C111.

`ai.py` (el "compute router": rutea chat a CodKing o Ollama y expone embeddings /
threat-detection / health-analysis / models / status) estaba al **44%** — la ruta de
decisión, ambos helpers de chat y los 4 endpoints sin cubrir. Este módulo los ejerce con
un `http_client` mockeado (el único borde externo), asertando el ruteo, el shape de
respuesta y los mapeos de error (502/504).

El router monta `verify_auth` como dependency → se pasa `TEST_API_KEY` (registrado en el
api_key_manager por conftest). `asyncio_mode=auto` (pyproject) → sin marcador.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import ai
from tests.conftest import TEST_API_KEY

_AUTH = {"X-API-Key": TEST_API_KEY}


def _resp(status: int = 200, payload=None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    return r


def _client(*, post=None, get=None) -> AsyncMock:
    """http_client falso: `post`/`get` devuelven la respuesta dada o lanzan si es excepción."""
    c = AsyncMock()
    if post is not None:
        c.post = AsyncMock(side_effect=post) if isinstance(post, BaseException) else AsyncMock(return_value=post)
    if get is not None:
        c.get = AsyncMock(side_effect=get) if isinstance(get, BaseException) else AsyncMock(return_value=get)
    return c


def _app(client: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(ai.router, prefix="/api/v1")
    app.state.http_client = client
    return app


async def _call(client: AsyncMock, method: str, path: str, **kw):
    async with AsyncClient(
        transport=ASGITransport(app=_app(client)), base_url="http://test"
    ) as ac:
        return await getattr(ac, method)(f"/api/v1/ai{path}", headers=_AUTH, **kw)


# =============================================================================
# /status
# =============================================================================


async def test_status_reports_ollama_available_and_codking_cores():
    client = _client(get=_resp(200, {"models": [{"name": "llama3"}, {"name": "bge"}]}))
    r = await _call(client, "get", "/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama"]["available"] is True
    assert body["ollama"]["models"] == ["llama3", "bge"]
    assert "compute_router" in body
    assert body["codking"]["cores"] == ["salud", "educacion", "ciberseguridad"]


async def test_status_ollama_failure_is_swallowed():
    client = _client(get=httpx.ConnectError("down"))
    r = await _call(client, "get", "/status")
    assert r.status_code == 200
    assert r.json()["ollama"]["available"] is False  # degrada, no 500


# =============================================================================
# /chat — el ruteo CodKing vs Ollama
# =============================================================================


async def test_chat_routes_to_codking_when_core_set(monkeypatch):
    monkeypatch.setattr(ai.settings, "codking_enabled", True, raising=False)
    client = _client(post=_resp(200, {"response": "malware", "confidence": 0.9, "scores": {"x": 1}}))
    r = await _call(client, "post", "/chat", json={
        "messages": [{"role": "user", "content": "scan"}], "core": "ciberseguridad"
    })
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "codking"
    assert body["core"] == "ciberseguridad"
    assert body["message"]["content"] == "malware"
    # llamó al /classify de security, no a ollama
    assert "/classify" in client.post.await_args.args[0]


async def test_chat_routes_to_ollama_without_core():
    client = _client(post=_resp(200, {
        "message": {"content": "hola"}, "prompt_eval_count": 3, "eval_count": 5
    }))
    r = await _call(client, "post", "/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "ollama"
    assert body["message"]["content"] == "hola"
    assert body["usage"]["completion_tokens"] == 5
    assert "/api/chat" in client.post.await_args.args[0]


async def test_chat_routes_to_ollama_when_codking_disabled(monkeypatch):
    """Con core pero codking_enabled=False, cae a Ollama (la condición es AND)."""
    monkeypatch.setattr(ai.settings, "codking_enabled", False, raising=False)
    client = _client(post=_resp(200, {"message": {"content": "x"}}))
    r = await _call(client, "post", "/chat", json={
        "messages": [{"role": "user", "content": "hi"}], "core": "salud"
    })
    assert r.status_code == 200
    assert r.json()["provider"] == "ollama"


async def test_chat_ollama_non_200_maps_to_502():
    client = _client(post=_resp(500, {}))
    r = await _call(client, "post", "/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 502


async def test_chat_ollama_timeout_maps_to_504():
    client = _client(post=httpx.TimeoutException("slow"))
    r = await _call(client, "post", "/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 504


async def test_chat_codking_non_200_maps_to_502(monkeypatch):
    monkeypatch.setattr(ai.settings, "codking_enabled", True, raising=False)
    client = _client(post=_resp(503, {}))
    r = await _call(client, "post", "/chat", json={
        "messages": [{"role": "user", "content": "hi"}], "core": "salud"
    })
    assert r.status_code == 502


# =============================================================================
# /embeddings
# =============================================================================


async def test_embeddings_ok_reports_dimensions():
    client = _client(post=_resp(200, {"embeddings": [[0.1, 0.2, 0.3]]}))
    r = await _call(client, "post", "/embeddings", json={"texts": ["hi"]})
    assert r.status_code == 200
    body = r.json()
    assert body["embeddings"] == [[0.1, 0.2, 0.3]]
    assert body["dimensions"] == 3


async def test_embeddings_non_200_maps_to_502():
    client = _client(post=_resp(500, {}))
    r = await _call(client, "post", "/embeddings", json={"texts": ["hi"]})
    assert r.status_code == 502


# =============================================================================
# /threat-detection
# =============================================================================


async def test_threat_detection_passes_through_json():
    client = _client(post=_resp(200, {"threat": True, "score": 0.95}))
    r = await _call(client, "post", "/threat-detection", json={"log_content": "sshd fail"})
    assert r.status_code == 200
    assert r.json() == {"threat": True, "score": 0.95}
    assert "/detect_threat" in client.post.await_args.args[0]


async def test_threat_detection_non_200_maps_to_502():
    client = _client(post=_resp(500, {}))
    r = await _call(client, "post", "/threat-detection", json={"log_content": "x"})
    assert r.status_code == 502


# =============================================================================
# /health-analysis — dos rutas: con pregunta (bio-savant) / sin (ml-production)
# =============================================================================


async def test_health_analysis_with_question_uses_bio_savant():
    client = _client(post=_resp(200, {"answer": "ok"}))
    r = await _call(client, "post", "/health-analysis", json={
        "metrics": {"hr": 60}, "question": "how am I?"
    })
    assert r.status_code == 200
    assert "/bio-savant/chat" in client.post.await_args.args[0]


async def test_health_analysis_without_question_uses_ml_predict():
    client = _client(post=_resp(200, {"prediction": 1}))
    r = await _call(client, "post", "/health-analysis", json={"metrics": {"hr": 60}})
    assert r.status_code == 200
    assert "/ml-production/predict" in client.post.await_args.args[0]


async def test_health_analysis_non_200_maps_to_502():
    client = _client(post=_resp(500, {}))
    r = await _call(client, "post", "/health-analysis", json={"metrics": {}})
    assert r.status_code == 502


# =============================================================================
# /models
# =============================================================================


async def test_models_lists_ollama_codking_and_onnx(monkeypatch):
    monkeypatch.setattr(ai.settings, "codking_enabled", True, raising=False)
    client = _client(get=_resp(200, {"models": [{"name": "llama3", "size": 42}]}))
    r = await _call(client, "get", "/models")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama"][0]["name"] == "llama3"
    assert len(body["codking"]) == 3  # 3 cores cuando codking_enabled
    assert any(m["name"] == "energy_model" for m in body["onnx"])


async def test_models_ollama_failure_swallowed_still_returns(monkeypatch):
    monkeypatch.setattr(ai.settings, "codking_enabled", False, raising=False)
    client = _client(get=httpx.ConnectError("down"))
    r = await _call(client, "get", "/models")
    assert r.status_code == 200
    body = r.json()
    assert body["ollama"] == []  # falló pero no rompe
    assert body["codking"] == []  # deshabilitado
    assert body["onnx"]  # onnx siempre presente
