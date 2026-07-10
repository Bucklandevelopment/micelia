"""
Tests for PromptOSAgentRunner: los 4 agentes de Prompt OS (ingest, taxonomy,
archivist, builder) + el helper puro _extract_json.

La única frontera es el FrangelsOrchestrator, que se inyecta en el constructor
como AsyncMock cuyo .chat(...) devuelve un InferenceResult controlado. Sin red
ni proveedores reales.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.agents.prompt_os_agents as pos_module
from app.services.agents.prompt_os_agents import (
    PromptOSAgentRunner,
    _extract_json,
    get_prompt_os_runner,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(success=True, content='{"ok": true}', error=None):
    """InferenceResult-like mock."""
    r = MagicMock()
    r.success = success
    r.content = content
    r.error = error
    r.model = "llama-3.3-70b"
    r.provider_id = "groq"
    r.tokens_input = 10
    r.tokens_output = 20
    r.latency_ms = 123.4
    return r


def _runner_with(result):
    """Runner con un orchestrator mockeado que devuelve `result` en chat()."""
    orch = MagicMock()
    orch.chat = AsyncMock(return_value=result)
    return PromptOSAgentRunner(orchestrator=orch), orch


# ---------------------------------------------------------------------------
# _extract_json (puro)
# ---------------------------------------------------------------------------

def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_json_fence():
    text = 'Aquí tienes:\n```json\n{"a": 1, "b": [2]}\n```\nfin'
    assert _extract_json(text) == {"a": 1, "b": [2]}


def test_extract_json_with_bare_fence():
    text = '```\n{"x": "y"}\n```'
    assert _extract_json(text) == {"x": "y"}


def test_extract_json_prose_with_brace_block():
    text = 'El resultado es {"category": "note"} según el análisis.'
    assert _extract_json(text) == {"category": "note"}


def test_extract_json_empty_raises():
    with pytest.raises(ValueError, match="Empty response"):
        _extract_json("   ")


def test_extract_json_unparseable_raises():
    with pytest.raises(ValueError, match="Could not parse JSON"):
        _extract_json("esto no tiene ningun json valido")


# ---------------------------------------------------------------------------
# orchestrator property (lazy)
# ---------------------------------------------------------------------------

def test_orchestrator_property_lazy(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(pos_module, "get_frangels_orchestrator", lambda: sentinel)
    runner = PromptOSAgentRunner()  # sin orchestrator
    assert runner.orchestrator is sentinel


def test_orchestrator_property_uses_injected():
    orch = MagicMock()
    runner = PromptOSAgentRunner(orchestrator=orch)
    assert runner.orchestrator is orch


# ---------------------------------------------------------------------------
# _call_agent
# ---------------------------------------------------------------------------

async def test_call_agent_unknown_raises():
    runner, _ = _runner_with(_result())
    with pytest.raises(ValueError, match="Unknown agent"):
        await runner._call_agent("does-not-exist", "hola")


async def test_call_agent_success_parses_and_meta():
    runner, orch = _runner_with(_result(content='{"clean_text": "hi"}'))
    out = await runner._call_agent("ingest", "raw")
    assert out["data"] == {"clean_text": "hi"}
    assert out["model_used"] == "llama-3.3-70b"
    assert out["provider_used"] == "groq"
    assert out["tokens_input"] == 10
    # se envió system + user
    sent = orch.chat.call_args.kwargs["messages"]
    assert sent[0]["role"] == "system"
    assert sent[1]["content"] == "raw"


async def test_call_agent_inference_failure_raises_runtime():
    runner, _ = _runner_with(_result(success=False, error="boom"))
    with pytest.raises(RuntimeError, match="inference failed"):
        await runner._call_agent("ingest", "raw")


async def test_call_agent_non_json_raises_value():
    runner, _ = _runner_with(_result(content="no json aqui"))
    with pytest.raises(ValueError, match="did not return valid JSON"):
        await runner._call_agent("ingest", "raw")


# ---------------------------------------------------------------------------
# run_ingest
# ---------------------------------------------------------------------------

async def test_run_ingest_empty_returns_fallback_without_call():
    runner, orch = _runner_with(_result())
    out = await runner.run_ingest("   ")
    assert out["data"]["detected_intent"] == "empty input"
    orch.chat.assert_not_awaited()


async def test_run_ingest_happy():
    payload = '{"type":"note","clean_text":"limpio","extracted_tags":["t"]}'
    runner, orch = _runner_with(_result(content=payload))
    out = await runner.run_ingest("texto crudo")
    assert out["data"]["clean_text"] == "limpio"
    orch.chat.assert_awaited_once()


async def test_run_ingest_failure_returns_fallback_with_error():
    runner, _ = _runner_with(_result(success=False, error="down"))
    out = await runner.run_ingest("texto crudo")
    assert out["data"]["detected_intent"] == "normalization failed"
    assert out["data"]["clean_text"] == "texto crudo"
    assert "error" in out


# ---------------------------------------------------------------------------
# run_taxonomy
# ---------------------------------------------------------------------------

async def test_run_taxonomy_happy():
    runner, orch = _runner_with(_result(content='{"category":"idea","priority":8}'))
    out = await runner.run_taxonomy({"content": "una idea", "tags": ["x"], "type": "note"})
    assert out["data"]["category"] == "idea"
    orch.chat.assert_awaited_once()


async def test_run_taxonomy_failure_fallback_keeps_tags():
    runner, _ = _runner_with(_result(content="basura"))
    out = await runner.run_taxonomy({"content": "c", "tags": ["keep"]})
    assert out["data"]["category"] == "note"
    assert out["data"]["tags"] == ["keep"]
    assert "error" in out


# ---------------------------------------------------------------------------
# run_archivist
# ---------------------------------------------------------------------------

async def test_run_archivist_happy():
    runner, _ = _runner_with(_result(content='{"should_persist": true, "summary": "s"}'))
    out = await runner.run_archivist({"content": "c", "output": "o", "tags": ["a"]})
    assert out["data"]["should_persist"] is True


async def test_run_archivist_failure_fallback():
    runner, _ = _runner_with(_result(success=False, error="nope"))
    out = await runner.run_archivist({"content": "c", "output": "o"})
    assert out["data"]["should_persist"] is False
    assert "error" in out


# ---------------------------------------------------------------------------
# run_builder
# ---------------------------------------------------------------------------

async def test_run_builder_empty_returns_fallback_without_call():
    runner, orch = _runner_with(_result())
    out = await runner.run_builder([])
    assert out["data"]["patterns_found"] == []
    orch.chat.assert_not_awaited()


async def test_run_builder_happy_truncates_content():
    runner, orch = _runner_with(
        _result(content='{"patterns_found":["p"],"proposed_skills":[],"proposed_mcp":[]}')
    )
    prompts = [{"content": "x" * 1000, "category": "note", "tags": ["t"]}]
    out = await runner.run_builder(prompts)
    assert out["data"]["patterns_found"] == ["p"]
    # el contenido enviado se trunca a 500 chars por prompt
    sent = orch.chat.call_args.kwargs["messages"][1]["content"]
    assert "x" * 500 in sent
    assert "x" * 501 not in sent


async def test_run_builder_failure_fallback():
    runner, _ = _runner_with(_result(content="no-json"))
    out = await runner.run_builder([{"content": "c"}])
    assert out["data"]["proposed_skills"] == []
    assert "error" in out


# ---------------------------------------------------------------------------
# get_prompt_os_runner singleton
# ---------------------------------------------------------------------------

def test_get_prompt_os_runner_singleton(monkeypatch):
    monkeypatch.setattr(pos_module, "_runner", None)
    a = get_prompt_os_runner()
    b = get_prompt_os_runner()
    assert a is b
    assert isinstance(a, PromptOSAgentRunner)
