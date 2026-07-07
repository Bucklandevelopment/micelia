"""
Crew Manager for Micelia Multi-Agent Orchestration.

Manages named crews — reusable configurations of agents and workflows
that can be executed against prompts.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.logging import log

from .agent_definitions import AGENT_DEFINITIONS
from .workflow_engine import WorkflowEngine
from .workflows import WORKFLOWS


class CrewManager:
    """
    Manages crews of agents and dispatches prompt execution through workflows.

    A crew is a named configuration binding a set of agents to a specific
    workflow. Crews are stored in memory and can be created, listed,
    retrieved, and executed against prompts.
    """

    def __init__(self, workflow_engine: WorkflowEngine):
        self._engine = workflow_engine
        self._crews: Dict[str, Dict[str, Any]] = {}

        # Create default crews on init
        self._create_default_crews()

    def _create_default_crews(self) -> None:
        """Seed the manager with sensible default crews."""
        self.create_crew(
            name="Quick",
            agents=["planner", "executor"],
            workflow="simple_execute",
        )
        self.create_crew(
            name="Standard",
            agents=["planner", "executor", "reviewer"],
            workflow="reviewed_execute",
        )
        self.create_crew(
            name="Full Review",
            agents=["planner", "executor", "reviewer", "critic", "patcher"],
            workflow="full_pipeline",
        )

    def create_crew(
        self,
        name: str,
        agents: List[str],
        workflow: str,
    ) -> Dict[str, Any]:
        """
        Create a new crew configuration.

        Args:
            name: Human-readable crew name.
            agents: List of agent role keys (must exist in AGENT_DEFINITIONS).
            workflow: Workflow name (must exist in WORKFLOWS).

        Returns:
            Dict describing the created crew.

        Raises:
            ValueError: If any agent or workflow is unknown.
        """
        # Validate agents
        unknown_agents = [a for a in agents if a not in AGENT_DEFINITIONS]
        if unknown_agents:
            raise ValueError(f"Unknown agents: {unknown_agents}")

        # Validate workflow
        if workflow not in WORKFLOWS:
            raise ValueError(
                f"Unknown workflow '{workflow}'. "
                f"Available: {list(WORKFLOWS.keys())}"
            )

        crew_id = str(uuid4())
        crew = {
            "crew_id": crew_id,
            "name": name,
            "agents": agents,
            "workflow": workflow,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "run_count": 0,
            "last_run_at": None,
        }

        self._crews[crew_id] = crew
        log.info(f"Crew created: '{name}' (id={crew_id}, workflow={workflow})")
        return crew

    def list_crews(self) -> List[Dict[str, Any]]:
        """Return all crews sorted by creation time."""
        return sorted(
            self._crews.values(),
            key=lambda c: c.get("created_at", ""),
        )

    def get_crew(self, crew_id: str) -> Optional[Dict[str, Any]]:
        """Return a crew by its ID, or None if not found."""
        return self._crews.get(crew_id)

    async def execute(
        self,
        prompt_id: str,
        crew_id: Optional[str] = None,
        workflow: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a prompt through a crew's workflow.

        If crew_id is provided, the crew's workflow is used (the workflow
        parameter is ignored). Otherwise, workflow defaults to
        'reviewed_execute'.

        Args:
            prompt_id: ID of the prompt to process.
            crew_id: Optional crew ID to use.
            workflow: Optional workflow name override (ignored if crew_id set).

        Returns:
            Workflow run result dict.
        """
        workflow_name = workflow or "reviewed_execute"

        if crew_id:
            crew = self._crews.get(crew_id)
            if not crew:
                return {
                    "run_id": str(uuid4()),
                    "status": "failed",
                    "error": f"Crew not found: {crew_id}",
                    "steps": [],
                    "total_duration_ms": 0,
                    "total_cost_usd": 0.0,
                }
            workflow_name = crew["workflow"]

        log.info(
            f"Executing prompt {prompt_id} with workflow '{workflow_name}'"
            + (f" (crew={crew_id})" if crew_id else "")
        )

        result = await self._engine.execute_workflow(
            prompt_id=prompt_id,
            workflow_name=workflow_name,
        )

        # Update crew stats
        if crew_id and crew_id in self._crews:
            self._crews[crew_id]["run_count"] += 1
            self._crews[crew_id]["last_run_at"] = (
                datetime.now(timezone.utc).isoformat()
            )

        return result


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_crew_manager: Optional[CrewManager] = None


def get_crew_manager(workflow_engine: Optional[WorkflowEngine] = None) -> CrewManager:
    """
    Return the singleton CrewManager instance.

    On first call, workflow_engine must be provided.
    Subsequent calls return the existing instance.
    """
    global _crew_manager
    if _crew_manager is None:
        if workflow_engine is None:
            raise RuntimeError(
                "CrewManager not initialized. "
                "Provide a WorkflowEngine on first call."
            )
        _crew_manager = CrewManager(workflow_engine)
    return _crew_manager
