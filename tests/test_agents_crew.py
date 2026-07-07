"""
Tests for the multi-agent orchestration building blocks.

Covers the pure-data agent/workflow registries and the in-memory CrewManager.
These modules have no external dependencies (no Redis/DB/LLM), so everything
runs deterministically with a mocked WorkflowEngine.
"""

from unittest.mock import AsyncMock

import pytest

from app.services.agents import agent_definitions as ad
from app.services.agents import crew_manager as cm_mod
from app.services.agents.agent_definitions import AGENT_DEFINITIONS, AgentDefinition
from app.services.agents.crew_manager import CrewManager, get_crew_manager
from app.services.agents.workflows import WORKFLOWS, WorkflowDefinition, WorkflowStep

# ---------------------------------------------------------------------------
# Agent definitions (pure data)
# ---------------------------------------------------------------------------

EXPECTED_AGENTS = {
    "planner", "executor", "reviewer", "critic", "patcher",
    "ingest", "taxonomy", "archivist", "builder",
}


def test_all_nine_agents_defined():
    assert set(AGENT_DEFINITIONS) == EXPECTED_AGENTS
    assert len(AGENT_DEFINITIONS) == 9


def test_agent_key_matches_role():
    for key, agent in AGENT_DEFINITIONS.items():
        assert isinstance(agent, AgentDefinition)
        assert agent.role == key


@pytest.mark.parametrize("key", sorted(EXPECTED_AGENTS))
def test_agent_fields_non_empty(key):
    agent = AGENT_DEFINITIONS[key]
    assert agent.name
    assert agent.description
    assert agent.system_prompt
    assert agent.capabilities
    assert all(isinstance(c, str) and c for c in agent.capabilities)


def test_agent_definition_defaults_to_empty_capabilities():
    bare = ad.AgentDefinition(
        name="X", role="x", description="d", system_prompt="s"
    )
    assert bare.capabilities == []


# ---------------------------------------------------------------------------
# Workflow definitions (pure data)
# ---------------------------------------------------------------------------

EXPECTED_WORKFLOWS = {
    "simple_execute", "reviewed_execute", "full_pipeline",
    "propose_skill", "propose_mcp",
}


def test_all_five_workflows_defined():
    assert set(WORKFLOWS) == EXPECTED_WORKFLOWS


def test_workflows_are_well_formed():
    for workflow in WORKFLOWS.values():
        assert isinstance(workflow, WorkflowDefinition)
        assert workflow.name
        assert workflow.description
        assert workflow.steps
        assert workflow.max_retries >= 0
        for step in workflow.steps:
            assert isinstance(step, WorkflowStep)
            # Every step's agent must be a real agent definition.
            assert step.agent in AGENT_DEFINITIONS
            assert step.action


def test_workflow_step_transitions_point_to_real_steps():
    """next_on_success / next_on_failure must be None (done) or a known action."""
    for workflow in WORKFLOWS.values():
        actions = {step.action for step in workflow.steps}
        for step in workflow.steps:
            for target in (step.next_on_success, step.next_on_failure):
                assert target is None or target in actions


def test_workflow_step_optional_failure_defaults_none():
    step = WorkflowStep(agent="planner", action="plan", next_on_success=None)
    assert step.next_on_failure is None


# ---------------------------------------------------------------------------
# CrewManager (in-memory, mocked engine)
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    return CrewManager(AsyncMock())


def test_default_crews_seeded(manager):
    crews = manager.list_crews()
    names = {c["name"] for c in crews}
    assert names == {"Quick", "Standard", "Full Review"}
    assert len(crews) == 3


def test_create_and_get_crew(manager):
    crew = manager.create_crew(
        name="Custom", agents=["planner", "executor"], workflow="simple_execute"
    )
    fetched = manager.get_crew(crew["crew_id"])
    assert fetched is not None
    assert fetched["name"] == "Custom"
    assert fetched["run_count"] == 0
    assert fetched["last_run_at"] is None


def test_get_unknown_crew_returns_none(manager):
    assert manager.get_crew("does-not-exist") is None


def test_create_crew_rejects_unknown_agent(manager):
    with pytest.raises(ValueError, match="Unknown agents"):
        manager.create_crew(
            name="Bad", agents=["planner", "ghost"], workflow="simple_execute"
        )


def test_create_crew_rejects_unknown_workflow(manager):
    with pytest.raises(ValueError, match="Unknown workflow"):
        manager.create_crew(
            name="Bad", agents=["planner"], workflow="no_such_workflow"
        )


async def test_execute_with_crew_id_uses_crew_workflow(manager):
    engine = manager._engine
    engine.execute_workflow.return_value = {"status": "completed", "run_id": "r1"}
    crew = manager.create_crew(
        name="Exec", agents=["planner", "executor"], workflow="simple_execute"
    )

    result = await manager.execute(prompt_id="p1", crew_id=crew["crew_id"])

    assert result["status"] == "completed"
    engine.execute_workflow.assert_awaited_once_with(
        prompt_id="p1", workflow_name="simple_execute"
    )
    # Stats updated on the crew.
    refreshed = manager.get_crew(crew["crew_id"])
    assert refreshed["run_count"] == 1
    assert refreshed["last_run_at"] is not None


async def test_execute_unknown_crew_returns_failed(manager):
    result = await manager.execute(prompt_id="p1", crew_id="missing")
    assert result["status"] == "failed"
    assert "Crew not found" in result["error"]
    manager._engine.execute_workflow.assert_not_awaited()


async def test_execute_without_crew_defaults_workflow(manager):
    engine = manager._engine
    engine.execute_workflow.return_value = {"status": "completed"}

    await manager.execute(prompt_id="p2")

    engine.execute_workflow.assert_awaited_once_with(
        prompt_id="p2", workflow_name="reviewed_execute"
    )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

def test_get_crew_manager_requires_engine_first(monkeypatch):
    monkeypatch.setattr(cm_mod, "_crew_manager", None)
    with pytest.raises(RuntimeError, match="not initialized"):
        get_crew_manager()


def test_get_crew_manager_returns_singleton(monkeypatch):
    monkeypatch.setattr(cm_mod, "_crew_manager", None)
    first = get_crew_manager(AsyncMock())
    second = get_crew_manager()
    assert first is second
