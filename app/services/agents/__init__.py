"""
Multi-Agent Orchestration system for Micelia (Phase 6).

Provides a multi-agent pipeline with Planner, Executor, Reviewer,
Critic, and Patcher agents that collaborate through configurable
workflows managed by the CrewManager.
"""

from .agent_definitions import AGENT_DEFINITIONS
from .crew_manager import CrewManager, get_crew_manager
from .workflow_engine import WorkflowEngine
from .workflows import WORKFLOWS

__all__ = [
    "CrewManager",
    "get_crew_manager",
    "AGENT_DEFINITIONS",
    "WORKFLOWS",
    "WorkflowEngine",
]
