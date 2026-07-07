"""
Workflow Definitions for Micelia Multi-Agent Orchestration.

Defines 5 workflow types as step graphs:
- simple_execute: planner -> executor -> done
- reviewed_execute: planner -> executor -> reviewer -> done/retry
- full_pipeline: planner -> executor -> reviewer -> critic -> patcher -> done
- propose_skill: taxonomy -> builder (detect pattern) -> executor (generate template) -> done
- propose_mcp: taxonomy -> builder (detect tool need) -> executor (generate spec) -> done
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class WorkflowStep:
    """A single step in a workflow graph."""
    agent: str
    action: str
    next_on_success: Optional[str]
    next_on_failure: Optional[str] = None


@dataclass
class WorkflowDefinition:
    """Definition of a complete workflow."""
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    max_retries: int = 1


WORKFLOWS: Dict[str, WorkflowDefinition] = {
    "simple_execute": WorkflowDefinition(
        name="Simple Execute",
        description=(
            "Minimal pipeline: the Planner analyzes the prompt and the Executor "
            "produces the output. No review or critique step. Best for simple, "
            "low-risk prompts."
        ),
        steps=[
            WorkflowStep(
                agent="planner",
                action="analyze_and_plan",
                next_on_success="execute",
                next_on_failure=None,
            ),
            WorkflowStep(
                agent="executor",
                action="execute",
                next_on_success=None,  # None = done
                next_on_failure=None,
            ),
        ],
        max_retries=0,
    ),
    "reviewed_execute": WorkflowDefinition(
        name="Reviewed Execute",
        description=(
            "Standard pipeline: Planner analyzes, Executor produces output, "
            "and the Reviewer validates quality. If the review score is below "
            "threshold, the Executor retries. Good for work and planning prompts."
        ),
        steps=[
            WorkflowStep(
                agent="planner",
                action="analyze_and_plan",
                next_on_success="execute",
                next_on_failure=None,
            ),
            WorkflowStep(
                agent="executor",
                action="execute",
                next_on_success="review",
                next_on_failure=None,
            ),
            WorkflowStep(
                agent="reviewer",
                action="review",
                next_on_success=None,  # done
                next_on_failure="execute",  # retry execution
            ),
        ],
        max_retries=1,
    ),
    "full_pipeline": WorkflowDefinition(
        name="Full Pipeline",
        description=(
            "Complete multi-agent pipeline: Planner analyzes, Executor produces, "
            "Reviewer validates quality, Critic checks for hallucinations and "
            "inconsistencies, and Patcher applies corrections. Best for high-stakes "
            "prompts where accuracy is critical."
        ),
        steps=[
            WorkflowStep(
                agent="planner",
                action="analyze_and_plan",
                next_on_success="execute",
                next_on_failure=None,
            ),
            WorkflowStep(
                agent="executor",
                action="execute",
                next_on_success="review",
                next_on_failure=None,
            ),
            WorkflowStep(
                agent="reviewer",
                action="review",
                next_on_success="critique",
                next_on_failure="execute",
            ),
            WorkflowStep(
                agent="critic",
                action="critique",
                next_on_success="patch",
                next_on_failure="patch",  # always patch after critique
            ),
            WorkflowStep(
                agent="patcher",
                action="patch",
                next_on_success=None,  # done
                next_on_failure=None,
            ),
        ],
        max_retries=1,
    ),
    "propose_skill": WorkflowDefinition(
        name="Propose Skill",
        description=(
            "Special workflow for detecting recurring patterns and proposing "
            "reusable skills. The Taxonomy agent classifies the prompt, then the "
            "Builder agent analyzes recent similar prompts to detect a pattern, "
            "and the Executor generates a skill template with trigger regex."
        ),
        steps=[
            WorkflowStep(
                agent="taxonomy",
                action="classify",
                next_on_success="detect_pattern",
                next_on_failure=None,
            ),
            WorkflowStep(
                agent="builder",
                action="detect_pattern",
                next_on_success="generate_skill",
                next_on_failure=None,  # no pattern found, end gracefully
            ),
            WorkflowStep(
                agent="executor",
                action="generate_skill",
                next_on_success=None,  # done
                next_on_failure=None,
            ),
        ],
        max_retries=0,
    ),
    "propose_mcp": WorkflowDefinition(
        name="Propose MCP",
        description=(
            "Special workflow for detecting when a prompt needs external tools "
            "and proposing an MCP server spec. The Taxonomy agent classifies, "
            "the Builder detects the need for external operations, and the "
            "Executor generates a MCP server specification."
        ),
        steps=[
            WorkflowStep(
                agent="taxonomy",
                action="classify",
                next_on_success="detect_tool_need",
                next_on_failure=None,
            ),
            WorkflowStep(
                agent="builder",
                action="detect_tool_need",
                next_on_success="generate_mcp_spec",
                next_on_failure=None,  # no tool needed, end gracefully
            ),
            WorkflowStep(
                agent="executor",
                action="generate_mcp_spec",
                next_on_success=None,  # done
                next_on_failure=None,
            ),
        ],
        max_retries=0,
    ),
}
