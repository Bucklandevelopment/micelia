"""
Dashboard API: aggregated Mission Control summary endpoint.

Combines prompt activity, budget status, queue preview, and service health
into a single API call optimized for the frontend dashboard.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request

from app.core.logging import log
from app.core.security import verify_auth

router = APIRouter(prefix="/dashboard", dependencies=[Depends(verify_auth)])


@router.get("/summary")
async def mission_control_summary(request: Request):
    """
    Aggregated summary for the Mission Control dashboard.
    Returns all data needed for the home page in a single call.
    """
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "activity": await _get_activity(request),
        "budget": _get_budget(request),
        "queue_preview": await _get_queue_preview(request),
        "recent_results": await _get_recent_results(request),
        "agents": _get_agent_status(request),
        "calendar_upcoming": await _get_calendar_upcoming(request),
    }
    return result


async def _get_activity(request: Request) -> dict:
    """Prompt activity counts."""
    prompt_store = getattr(request.app.state, "prompt_store", None)
    if not prompt_store:
        return {"captured_today": 0, "processed_today": 0, "failed_today": 0, "pending": 0, "queued": 0}

    try:
        counts = {"captured_today": 0, "processed_today": 0, "failed_today": 0, "pending": 0, "queued": 0}

        # Get pending count
        pending = await prompt_store.list_prompts(status="pending", limit=0)
        if pending and isinstance(pending, dict):
            counts["pending"] = pending.get("total", 0)

        # Get queued count
        queued = await prompt_store.list_prompts(status="queued", limit=0)
        if queued and isinstance(queued, dict):
            counts["queued"] = queued.get("total", 0)

        # Get captured count
        captured = await prompt_store.list_prompts(status="captured", limit=0)
        if captured and isinstance(captured, dict):
            counts["captured_today"] = captured.get("total", 0)

        # Get today's completed/failed from executor
        executor = getattr(request.app.state, "prompt_executor", None)
        if executor:
            counts["processed_today"] = getattr(executor, "completed_today", 0)
            counts["failed_today"] = getattr(executor, "failed_today", 0)

        return counts
    except Exception as e:
        log.warning(f"Dashboard activity error: {e}")
        return {"captured_today": 0, "processed_today": 0, "failed_today": 0, "pending": 0, "queued": 0}


def _get_budget(request: Request) -> dict:
    """Budget status from policy engine."""
    try:
        from app.services.frangels.policy_engine import get_policy_engine
        engine = get_policy_engine()
        status = engine.get_status()
        budget = status.get("budget", {})
        return {
            "daily_spent": budget.get("spent_today_usd", 0),
            "daily_limit": budget.get("daily_limit_usd", 0),
            "monthly_spent": budget.get("spent_this_month_usd", 0),
            "monthly_limit": budget.get("monthly_limit_usd", 0),
        }
    except Exception:
        return {"daily_spent": 0, "daily_limit": 0, "monthly_spent": 0, "monthly_limit": 0}


async def _get_queue_preview(request: Request) -> list:
    """Next 5 prompts in queue."""
    prompt_store = getattr(request.app.state, "prompt_store", None)
    if not prompt_store:
        return []
    try:
        result = await prompt_store.list_prompts(status="queued", limit=5)
        prompts = result.get("prompts", []) if isinstance(result, dict) else []
        return [
            {
                "prompt_id": str(p.get("prompt_id", "")),
                "content": (p.get("content", ""))[:100],
                "category": p.get("category", "note"),
                "priority": p.get("priority", 5),
                "created_at": p.get("created_at", ""),
            }
            for p in prompts[:5]
        ]
    except Exception:
        return []


async def _get_recent_results(request: Request) -> list:
    """Last 5 completed prompts."""
    prompt_store = getattr(request.app.state, "prompt_store", None)
    if not prompt_store:
        return []
    try:
        result = await prompt_store.list_prompts(status="completed", limit=5)
        prompts = result.get("prompts", []) if isinstance(result, dict) else []
        return [
            {
                "prompt_id": str(p.get("prompt_id", "")),
                "content": (p.get("content", ""))[:100],
                "provider_used": p.get("provider_used", ""),
                "model_used": p.get("model_used", ""),
                "latency_ms": p.get("latency_ms"),
                "cost_usd": p.get("cost_usd"),
                "completed_at": p.get("completed_at", ""),
            }
            for p in prompts[:5]
        ]
    except Exception:
        return []


def _get_agent_status(request: Request) -> dict:
    """Status of background agents."""
    agent = getattr(request.app.state, "prompt_agent", None)
    executor = getattr(request.app.state, "prompt_executor", None)
    scheduler = getattr(request.app.state, "prompt_scheduler", None)

    return {
        "agent_running": getattr(agent, "is_running", False) if agent else False,
        "executor_running": getattr(executor, "is_running", False) if executor else False,
        "scheduler_running": getattr(scheduler, "is_running", False) if scheduler else False,
        "executor_active_count": getattr(executor, "active_count", 0) if executor else 0,
    }


async def _get_calendar_upcoming(request: Request) -> list:
    """Next 3 calendar events."""
    calendar_service = getattr(request.app.state, "google_calendar", None)
    if not calendar_service or not getattr(calendar_service, "is_connected", False):
        return []
    try:
        events = await calendar_service.get_upcoming_events(max_results=3)
        return [
            {
                "summary": e.get("summary", ""),
                "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                "end": e.get("end", {}).get("dateTime", ""),
            }
            for e in (events or [])[:3]
        ]
    except Exception:
        return []
