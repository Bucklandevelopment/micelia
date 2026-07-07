"""
API Router for the Multi-Agent Orchestration system (Phase 6).

Endpoints for managing crews, executing multi-agent workflows,
and inspecting run results.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.logging import log
from app.core.security import verify_auth
from app.services.agents.workflows import WORKFLOWS

router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
    dependencies=[Depends(verify_auth)],
)


# ==================== SCHEMAS ====================


class CrewCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    agents: List[str] = Field(
        ...,
        min_length=1,
        description="List of agent role keys (e.g. planner, executor).",
    )
    workflow: str = Field(
        ...,
        description="Workflow name (e.g. simple_execute, reviewed_execute, full_pipeline).",
    )


class ExecuteRequest(BaseModel):
    prompt_id: str = Field(..., description="ID of the prompt to process.")
    crew_id: Optional[str] = Field(
        None,
        description="Crew ID to use. If set, crew's workflow is used.",
    )
    workflow: Optional[str] = Field(
        None,
        description=(
            "Workflow name override (ignored if crew_id is set). "
            "Defaults to reviewed_execute."
        ),
    )


# ==================== HELPERS ====================


def _get_crew_manager(request: Request):
    """Resolve the CrewManager from app state."""
    mgr = getattr(request.app.state, "crew_manager", None)
    if mgr is None:
        raise HTTPException(
            status_code=503,
            detail="Multi-agent orchestration system not available.",
        )
    return mgr


def _get_workflow_engine(request: Request):
    """Resolve the WorkflowEngine from app state."""
    engine = getattr(request.app.state, "workflow_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail="Workflow engine not available.",
        )
    return engine


# ==================== CREW ENDPOINTS ====================


@router.get("/crews")
async def list_crews(request: Request):
    """List all configured crews."""
    mgr = _get_crew_manager(request)
    crews = mgr.list_crews()
    return {"crews": crews, "count": len(crews)}


@router.post("/crews")
async def create_crew(data: CrewCreate, request: Request):
    """Create a new crew with a name, agent list, and workflow."""
    mgr = _get_crew_manager(request)
    try:
        crew = mgr.create_crew(
            name=data.name,
            agents=data.agents,
            workflow=data.workflow,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return crew


# ==================== WORKFLOW ENDPOINTS ====================


@router.get("/workflows")
async def list_workflows():
    """List available workflow definitions."""
    result = []
    for key, wf in WORKFLOWS.items():
        result.append({
            "name": key,
            "display_name": wf.name,
            "description": wf.description,
            "max_retries": wf.max_retries,
            "steps": [
                {
                    "agent": s.agent,
                    "action": s.action,
                    "next_on_success": s.next_on_success,
                    "next_on_failure": s.next_on_failure,
                }
                for s in wf.steps
            ],
            "agents_used": list({s.agent for s in wf.steps}),
        })
    return {"workflows": result, "count": len(result)}


# ==================== EXECUTION ENDPOINTS ====================


@router.post("/execute")
async def execute_prompt(data: ExecuteRequest, request: Request):
    """
    Execute a prompt through a multi-agent workflow.

    Provide either a crew_id (uses the crew's workflow) or a workflow name.
    Defaults to the 'reviewed_execute' workflow if neither is given.
    """
    mgr = _get_crew_manager(request)

    result = await mgr.execute(
        prompt_id=data.prompt_id,
        crew_id=data.crew_id,
        workflow=data.workflow,
    )

    if result.get("status") == "failed":
        log.warning(
            f"Agent execution failed for prompt {data.prompt_id}: "
            f"{result.get('error', 'unknown')}"
        )

    return result


# ==================== RUN ENDPOINTS ====================


@router.get("/runs")
async def list_runs(
    request: Request,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List recent workflow runs."""
    engine = _get_workflow_engine(request)
    runs = engine.get_runs(limit=limit, offset=offset)

    return {
        "runs": [
            {
                "run_id": r["run_id"],
                "prompt_id": r.get("prompt_id"),
                "workflow": r.get("workflow"),
                "status": r["status"],
                "total_duration_ms": r.get("total_duration_ms"),
                "total_cost_usd": r.get("total_cost_usd"),
                "step_count": len(r.get("steps", [])),
                "started_at": r.get("started_at"),
                "completed_at": r.get("completed_at"),
            }
            for r in runs
        ],
        "count": len(runs),
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    """Get full detail of a specific workflow run."""
    engine = _get_workflow_engine(request)
    run = engine.get_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    return run
