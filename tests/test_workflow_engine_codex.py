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

from app.services.agents.agent_definitions import AGENT_DEFINITIONS
from app.services.agents.workflow_engine import WorkflowEngine
from app.services.agents.workflows import WORKFLOWS, WorkflowDefinition, WorkflowStep

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


# ---------------------------------------------------------------------------
# execute_workflow — graph edge cases (custom workflows via monkeypatch)
# ---------------------------------------------------------------------------


async def test_execute_unknown_agent_marks_step_failed(engine, monkeypatch):
    """A step referencing an agent not in AGENT_DEFINITIONS fails before any chat."""
    wf = WorkflowDefinition(
        name="Ghost",
        description="step points at a non-existent agent",
        steps=[
            WorkflowStep(
                agent="ghost",
                action="haunt",
                next_on_success=None,
                next_on_failure=None,
            ),
        ],
        max_retries=0,
    )
    monkeypatch.setitem(WORKFLOWS, "ghost_wf", wf)
    engine._prompt_store.get_prompt.return_value = {"content": "x"}

    result = await engine.execute_workflow("p1", workflow_name="ghost_wf")

    assert result["status"] == "failed"
    assert result["steps"][0]["error"] == "Unknown agent: ghost"
    engine._orchestrator.chat.assert_not_called()


async def test_execute_full_pipeline_covers_critic_branch(engine):
    """full_pipeline includes a critic step: exercises the _critic_requires_patch branch."""
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.side_effect = [
        _chat_dict(content="a plan"),                    # planner
        _chat_dict(content="an answer"),                 # executor
        _chat_dict(content='{"passed": true}'),          # reviewer -> critique
        _chat_dict(content='{"requires_patch": false}'), # critic -> patch
        _chat_dict(content="patched output"),            # patcher -> done
    ]

    result = await engine.execute_workflow("p1", workflow_name="full_pipeline")

    assert result["status"] == "completed"
    assert len(result["steps"]) == 5  # planner, executor, reviewer, critic, patcher
    assert [s["agent"] for s in result["steps"]] == [
        "planner", "executor", "reviewer", "critic", "patcher",
    ]


async def test_execute_critic_requiring_patch_still_routes_to_patch(engine):
    """A critic that flags a high-severity issue takes next_on_failure (also patch)."""
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.side_effect = [
        _chat_dict(content="a plan"),                # planner
        _chat_dict(content="an answer"),             # executor
        _chat_dict(content='{"passed": true}'),      # reviewer -> critique
        _chat_dict(content='{"severity": "high"}'),  # critic requires patch
        _chat_dict(content="patched output"),        # patcher -> done
    ]

    result = await engine.execute_workflow("p1", workflow_name="full_pipeline")

    assert result["status"] == "completed"
    assert result["steps"][-1]["agent"] == "patcher"


async def test_execute_next_action_unknown_marks_failed(engine, monkeypatch):
    """A step whose next_on_success names a non-existent action fails the run."""
    wf = WorkflowDefinition(
        name="Broken",
        description="next_on_success points to an unknown action",
        steps=[
            WorkflowStep(
                agent="planner",
                action="analyze_and_plan",
                next_on_success="nope",
                next_on_failure=None,
            ),
        ],
        max_retries=0,
    )
    monkeypatch.setitem(WORKFLOWS, "broken_wf", wf)
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.return_value = _chat_dict(content="a plan")

    result = await engine.execute_workflow("p1", workflow_name="broken_wf")

    assert result["status"] == "failed"


async def test_execute_retry_budget_exhausted_breaks(engine, monkeypatch):
    """A self-looping step with no retries left breaks after a single execution."""
    wf = WorkflowDefinition(
        name="Loop",
        description="step loops back onto itself",
        steps=[
            WorkflowStep(
                agent="executor",
                action="execute",
                next_on_success="execute",  # loops to index 0
                next_on_failure=None,
            ),
        ],
        max_retries=0,
    )
    monkeypatch.setitem(WORKFLOWS, "loop_wf", wf)
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.return_value = _chat_dict(content="answer")

    result = await engine.execute_workflow("p1", workflow_name="loop_wf")

    # Ran once; next_index(0) <= step_index(0) with retries 0 -> break.
    assert engine._orchestrator.chat.await_count == 1
    assert result["status"] == "completed"


async def test_execute_failure_path_retries_then_completes(engine, monkeypatch):
    """A failing step with a next_on_failure edge retries down the failure branch."""
    wf = WorkflowDefinition(
        name="Recover",
        description="first step fails, recovery step succeeds",
        steps=[
            WorkflowStep(
                agent="executor",
                action="execute",
                next_on_success=None,
                next_on_failure="recover",
            ),
            WorkflowStep(
                agent="patcher",
                action="recover",
                next_on_success=None,
                next_on_failure=None,
            ),
        ],
        max_retries=1,
    )
    monkeypatch.setitem(WORKFLOWS, "recover_wf", wf)
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.side_effect = [
        _chat_dict(content="", success=False),  # step0 fails -> failure path
        _chat_dict(content="recovered"),         # step1 succeeds -> done
    ]

    result = await engine.execute_workflow("p1", workflow_name="recover_wf")

    assert result["status"] == "completed"
    assert engine._orchestrator.chat.await_count == 2


# ---------------------------------------------------------------------------
# execute_workflow — audit checkpoint/end_session exceptions are swallowed
# ---------------------------------------------------------------------------


async def test_execute_checkpoint_failure_is_tolerated():
    audit = AsyncMock()
    audit.start_session.return_value = "sess-1"
    audit.checkpoint.side_effect = RuntimeError("checkpoint down")
    engine = WorkflowEngine(
        frangels_orchestrator=AsyncMock(),
        prompt_store=AsyncMock(),
        entire_service=audit,
    )
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.return_value = _chat_dict(content="done")

    result = await engine.execute_workflow("p1", workflow_name="simple_execute")

    # Checkpoint raised on every step but the run still completes.
    assert result["status"] == "completed"
    assert audit.checkpoint.await_count == 2
    audit.end_session.assert_awaited_once()


async def test_execute_end_session_failure_is_tolerated():
    audit = AsyncMock()
    audit.start_session.return_value = "sess-1"
    audit.end_session.side_effect = RuntimeError("end down")
    engine = WorkflowEngine(
        frangels_orchestrator=AsyncMock(),
        prompt_store=AsyncMock(),
        entire_service=audit,
    )
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.return_value = _chat_dict(content="done")

    result = await engine.execute_workflow("p1", workflow_name="simple_execute")

    # end_session raised but the run record is still returned intact.
    assert result["status"] == "completed"
    audit.end_session.assert_awaited_once()


# ---------------------------------------------------------------------------
# execute_workflow — run store trimming
# ---------------------------------------------------------------------------


async def test_execute_trims_runs_to_max(engine):
    engine._max_stored_runs = 1
    engine._prompt_store.get_prompt.return_value = {"content": "x"}
    engine._orchestrator.chat.return_value = _chat_dict(content="done")

    await engine.execute_workflow("p1", workflow_name="simple_execute")
    r2 = await engine.execute_workflow("p2", workflow_name="simple_execute")

    # Only the most recent run is kept.
    assert len(engine._runs) == 1
    assert engine._runs[0]["run_id"] == r2["run_id"]


# ---------------------------------------------------------------------------
# _build_messages — per-action prompt construction
# ---------------------------------------------------------------------------


def test_build_messages_covers_all_actions(engine):
    agent_def = AGENT_DEFINITIONS["executor"]
    context = {
        "user_prompt": "UP",
        "executor_output": "EO",
        "review": "RV",
        "critique": "CR",
        "taxonomy_result": "TX",
        "builder_output": "BO",
    }

    def user_content(action):
        messages = engine._build_messages(agent_def, action, context)
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == agent_def.system_prompt
        assert messages[-1]["role"] == "user"
        return messages[-1]["content"]

    critique = user_content("critique")
    assert "Critique the following response" in critique
    assert "EO" in critique

    patch = user_content("patch")
    assert "--- REVIEW ---" in patch
    assert "--- CRITIQUE ---" in patch
    assert "RV" in patch and "CR" in patch

    assert "Classify the following prompt" in user_content("classify")
    assert "recurring patterns" in user_content("detect_pattern")

    tool_need = user_content("detect_tool_need")
    assert "external" in tool_need
    assert "TX" in tool_need  # taxonomy_result interpolated

    gen_skill = user_content("generate_skill")
    assert "skill template" in gen_skill
    assert "BO" in gen_skill  # builder_output interpolated

    assert "MCP server specification" in user_content("generate_mcp_spec")

    # Unknown action falls through to the else branch: raw user prompt only.
    assert user_content("totally-unknown-action") == "UP"
