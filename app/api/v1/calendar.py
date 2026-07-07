"""
API Calendar: Google Calendar integration endpoints.

Provides OAuth2 flow, event management, and bi-directional
sync between Google Calendar and the prompt system.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.logging import log
from app.core.security import verify_auth
from app.services.google_calendar import get_google_calendar

router = APIRouter(prefix="/calendar", dependencies=[Depends(verify_auth)])


# === REQUEST/RESPONSE MODELS ===

class CreateEventRequest(BaseModel):
    calendar_id: str = Field(default="primary", description="Calendar ID")
    summary: str = Field(..., description="Event title")
    start: str = Field(..., description="ISO format start time")
    end: str = Field(..., description="ISO format end time")
    description: str = Field(default="", description="Event description")


# === AUTH ENDPOINTS ===

@router.get("/auth")
async def calendar_auth():
    """
    Returns Google OAuth2 authorization URL.
    User must visit this URL to grant calendar access.
    """
    gcal = get_google_calendar()

    try:
        result = await gcal.authenticate()
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Calendar auth error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")


@router.get("/callback")
async def calendar_callback(code: str = Query(..., description="OAuth2 authorization code")):
    """
    Handles Google OAuth2 callback.
    Exchanges authorization code for access token and saves it.
    """
    gcal = get_google_calendar()

    try:
        result = await gcal.handle_callback(code)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        log.error(f"Calendar callback error: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete OAuth2 callback")


# === STATUS ===

@router.get("/status")
async def calendar_status():
    """
    Returns Google Calendar connection status.
    Includes whether libs are installed, token exists, and last sync time.
    """
    gcal = get_google_calendar()
    return gcal.get_status()


# === CALENDARS ===

@router.get("/calendars")
async def list_calendars():
    """
    Lists all calendars accessible by the connected Google account.
    """
    gcal = get_google_calendar()

    if not gcal.is_connected():
        raise HTTPException(
            status_code=403,
            detail="Google Calendar not connected. Use /calendar/auth first."
        )

    try:
        calendars = await gcal.list_calendars()
        return {"calendars": calendars, "count": len(calendars)}
    except Exception as e:
        log.error(f"List calendars error: {e}")
        raise HTTPException(status_code=500, detail="Failed to list calendars")


# === EVENTS ===

@router.get("/events")
async def get_events(
    calendar_id: str = Query(default="primary", description="Calendar ID"),
    date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format (defaults to today)"),
    days: int = Query(default=7, ge=1, le=90, description="Number of days to fetch"),
):
    """
    Get events from a calendar.
    If date is provided, returns events starting from that date.
    Otherwise returns events from now for the specified number of days.
    """
    gcal = get_google_calendar()

    if not gcal.is_connected():
        raise HTTPException(
            status_code=403,
            detail="Google Calendar not connected. Use /calendar/auth first."
        )

    try:
        if date:
            try:
                start_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
            time_min = start_date.isoformat()
        else:
            time_min = datetime.now(timezone.utc).isoformat()

        time_min_dt = datetime.fromisoformat(time_min.replace("Z", "+00:00"))
        time_max = (time_min_dt + timedelta(days=days)).isoformat()

        events = await gcal.get_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
        )

        return {
            "events": events,
            "count": len(events),
            "calendar_id": calendar_id,
            "time_min": time_min,
            "time_max": time_max,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Get events error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get events")


@router.post("/events")
async def create_event(request: CreateEventRequest):
    """
    Create a new event in the specified calendar.
    """
    gcal = get_google_calendar()

    if not gcal.is_connected():
        raise HTTPException(
            status_code=403,
            detail="Google Calendar not connected. Use /calendar/auth first."
        )

    try:
        event = await gcal.create_event(
            calendar_id=request.calendar_id,
            summary=request.summary,
            start=request.start,
            end=request.end,
            description=request.description,
        )
        return {"success": True, "event": event}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"Create event error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create event")


# === SYNC ===

@router.post("/sync")
async def trigger_sync():
    """
    Trigger bi-directional sync between Google Calendar and prompts.

    - FROM calendar: reads events with [PROMPT] in summary, creates prompts
    - TO calendar: writes completed prompt results as events
    """
    gcal = get_google_calendar()

    if not gcal.is_connected():
        raise HTTPException(
            status_code=403,
            detail="Google Calendar not connected. Use /calendar/auth first."
        )

    try:
        from_result = await gcal.sync_prompts_from_calendar()
        to_result = await gcal.sync_results_to_calendar()

        return {
            "success": True,
            "from_calendar": from_result,
            "to_calendar": to_result,
        }

    except Exception as e:
        log.error(f"Calendar sync error: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync with Google Calendar")


# === DISCONNECT ===

@router.delete("/disconnect")
async def disconnect_calendar():
    """
    Disconnect Google Calendar by removing stored OAuth2 token.
    """
    gcal = get_google_calendar()

    try:
        result = await gcal.disconnect()
        return result
    except Exception as e:
        log.error(f"Calendar disconnect error: {e}")
        raise HTTPException(status_code=500, detail="Failed to disconnect Google Calendar")
