"""
Tests for WorkflowEngine (app.services.agents.workflow_engine).

All of the engine's collaborators (frangels orchestrator, prompt_store, entire_service)
are constructor-injected, so nothing touches Postgres/Redis/httpx — they are replaced
with AsyncMock. Chat results are exercised as BOTH dicts and attribute-style objects,
since the engine handles either shape.

Covers:
  - Pure helpers: _reviewer_passed, _critic_requires_patch, _find_step_index,
    _update_context, get_runs, get_run
  - execute_workflow: unknown workflow, prompt-not-found, happy path, reviewer-fail
    retry path, orchestrator exception, and the audit (entire_service) branches
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.agents.workflow_engine import WorkflowEngine
from app.services.agents.workflows import WORKFLOWS

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def engine():
    """Engine with mocked collaborators and no audit service."""
    return WorkflowEngine(
        frangels_orchestrator=AsyncMock(),
        prompt_store=AsyncMock(),
        entire_service=None,
    )


def _chat_dict(content="output", success=True, **extra):
    """A chat result in dict shape."""
    base = {
        "success": success,
        "content": content,
        "tokens_input": 10,
        "tokens_output": 20,
        "model": "test-model",
        "provider_id": "groq",
        "error": None,
    }
    base.update(extra)
    return base


def _chat_obj(content="output", success=True):
    """A chat result in attribute (object) shape."""
    return SimpleNamespace(
        success=success,
        content=content,
        tokens_input=10,
        tokens_output=20,
        model="test-model",
        provider_id="groq",
        error=None,
    )


# ---------------------------------------------------------------------------
# _reviewer_passed
# ---------------------------------------------------------------------------


def test_reviewer_passed_json_passed_field(engine):
    assert engine._reviewer_passed('{"passed": true}') is True
    assert engine._reviewer_passed('{"passed": false}') is False


def test_reviewer_passed_json_score_threshold(engine):
    assert engine._reviewer_passed('{"score": 0.9}') is True
    assert engine._reviewer_passed('{"score": 0.7}') is True
    assert engine._reviewer_passed('{"score": 0.5}') is False


def test_reviewer_passed_keyword_fallback(engine):
    assert engine._reviewer_passed("The response is approved") is True
    assert engine._reviewer_passed("This was rejected") is False


def test_reviewer_passed_default_true_when_ambiguous(engine):
    assert engine._reviewer_passed("some unstructured text") is True


# ---------------------------------------------------------------------------
# _critic_requires_patch
# ---------------------------------------------------------------------------


def test_critic_requires_patch_json_flag(engine):
    assert engine._critic_requires_patch('{"requires_patch": true}') is True
    assert engine._critic_requires_patch('{"requires_patch": false}') is False


def test_critic_requires_patch_severity(engine):
    assert engine._critic_requires_patch('{"severity": "high"}') is True
    assert engine._critic_requires_patch('{"severity": "medium"}') is True
    assert engine._critic_requires_patch('{"severity": "critical"}') is True
    assert engine._critic_requires_patch('{"severity": "low"}') is False


def test_critic_requires_patch_default_false(engine):
    assert engine._critic_requires_patch("looks fine to me") is False


# ---------------------------------------------------------------------------
# _find_step_index / _update_context
# ---------------------------------------------------------------------------


def test_find_step_index(engine):
    wf = WORKFLOWS["reviewed_execute"]
    assert engine._find_step_index(wf, "analyze_and_plan") == 0
    assert engine._find_step_index(wf, "execute") == 1
    assert engine._find_step_index(wf, "review") == 2
    assert engine._find_step_index(wf, "no-such-action") is None


def test_update_context_routes_each_agent_role(engine):
    context = {}
    for agent, key in [
        ("planner", "plan"),
        ("executor", "executor_output"),
        ("reviewer", "review"),
        ("critic", "critique"),
        ("patcher", "patched_output"),
        ("taxonomy", "taxonomy_result"),
        ("builder", "builder_output"),
    ]:
        engine._update_context(context, agent, f"{agent}-content")
        assert context[key] == f"{agent}-content"


def test_update_context_unknown_agent_is_noop(engine):
    context = {"plan": "keep"}
    engine._update_context(context, "unknown-role", "ignored")
    assert context == {"plan": "keep"}


# ---------------------------------------------------------------------------
# get_runs / get_run
# ---------------------------------------------------------------------------


def test_get_runs_sorted_desc_with_offset_and_limit(engine):
    engine._runs = [
        {"run_id": "a", "started_at": "2026-01-01T00:00:00"},
        {"run_id": "b", "started_at": "2026-03-01T00:00:00"},
        {"run_id": "c", "started_at": "2026-02-01T00:00:00"},
    ]
    ordered = engine.get_runs(limit=2, offset=0)
    assert [r["run_id"] for r in ordered] == ["b", "c"]
    assert [r["run_id"] for r in engine.get_runs(limit=2, offset=1)] == ["c", "a"]


def test_get_run_by_id(engine):
    engine._runs = [{"run_id": "a", "started_at": "2026-01-01T00:00:00"}]
    assert engine.get_run("a")["run_id"] == "a"
    assert engine.get_run("missing") is None


# ---------------------------------------------------------------------------
# execute_workflow
# ---------------------------------------------------------------------------


async def test_execute_unknown_workflow_returns_failed(engine):
    result = await engine.execute_workflow("p1", workflow_name="does-not-exist")
    assert result["status"] == "failed"
    assert "Unknown workflow" in result["error"]
    engine._prompt_store.get_prompt.assert_not_called()


async def test_execute_prompt_not_found(engine):
    engine._prompt_store.get_prompt.return_value = None
    result = await engine.execute_workflow("p1", workflow_name="reviewed_execute")
    assert result["status"] == "failed"
    assert "Prompt not found" in result["error"]


async def test_execute_simple_happy_path_object_result(engine):
    engine._prompt_store.get_prompt.return_value = {"content": "do the thing"}
    engine._orchestrator.chat.return_value = _chat_obj(content="done")

    result = await engine.execute_workflow("p1", workflow_name="simple_execute")

    assert result["status"] == "completed"
    assert len(result["steps"]) == 2  # planner + executor
    assert result["final_output"] == "done"  # executor_output
    assert engine._orchestrator.chat.await_count == 2
    # Run is stored and retrievable.
    assert engine.get_run(result["run_id"]) is not None


async def test_execute_reviewed_happy_path_dict_result(engine):
    engine._prompt_store.get_prompt.return_value = {"content": "do the thing"}
    engine._orchestrator.chat.side_effect = [
        _chat_dict(content="a plan"),
        _chat_dict(content="an answer"),
        _chat_dict(content='{"passed": true}'),
    ]

    result = await engine.execute_workflow("p1", workflow_name="reviewed_execute")

    assert result["status"] == "completed"
    assert len(result["steps"]) == 3  # planner + executor + reviewer


async def test_execute_reviewed_retry_then_pass(engine):
    engine._prompt_store.get_prompt.return_value = {"content": "do the thing"}
    engine._orchestrator.chat.side_effect = [
        _chat_dict(content="a plan"),
        _chat_dict(content="first answer"),
        _chat_dict(content='{"passed": false}'),  # reviewer fails -> retry execute
        _chat_dict(content="second answer"),
        _chat_dict(content='{"passed": true}'),  # reviewer passes
    ]

    result = await engine.execute_workflow("p1", workflow_name="reviewed_execute")

    assert result["status"] == "completed"
    # planner, executor, reviewer(fail), executor, reviewer(pass)
    assert len(result["steps"]) == 5
    assert engine._orchestrator.chat.await_count == 5


async def test_execute_orchestrator_exception_marks_failed(engine):
    engine._prompt_store.get_prompt.return_value = {"content": "do the thing"}
    engine._orchestrator.chat.side_effect = RuntimeError("boom")

    result = await engine.execute_workflow("p1", workflow_name="simple_execute")

    assert result["status"] == "failed"
    assert len(result["steps"]) == 1  # planner step failed, no failure path -> stop
    assert result["steps"][0]["error"] == "boom"


async def test_execute_audit_session_lifecycle_invoked():
    audit = AsyncMock()
    audit.start_session.return_value = "sess-1"
    engine = WorkflowEngine(
        frangels_orchestrator=AsyncMock(),
        prompt_store=AsyncMock(),
        entire_service=audit,
    )
    engine._prompt_store.get_prompt.return_value = {"content": "do the thing"}
    engine._orchestrator.chat.return_value = _chat_dict(content="done")

    result = await engine.execute_workflow("p1", workflow_name="simple_execute")

    audit.start_session.assert_awaited_once()
    assert audit.checkpoint.await_count == 2  # one per completed step
    audit.end_session.assert_awaited_once_with("sess-1", result["status"])


async def test_execute_audit_start_failure_is_tolerated():
    audit = AsyncMock()
    audit.start_session.side_effect = RuntimeError("audit down")
    engine = WorkflowEngine(
        frangels_orchestrator=AsyncMock(),
        prompt_store=AsyncMock(),
        entire_service=audit,
    )
    engine._prompt_store.get_prompt.return_value = {"content": "do the thing"}
    engine._orchestrator.chat.return_value = _chat_dict(content="done")

    result = await engine.execute_workflow("p1", workflow_name="simple_execute")

    # Workflow still completes; checkpoint/end guarded by audit_session_id (None).
    assert result["status"] == "completed"
    audit.checkpoint.assert_not_called()
