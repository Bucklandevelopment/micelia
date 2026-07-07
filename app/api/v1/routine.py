"""
API Routine: Daily routine sync to Google Calendar.

Parses the rutina-diaria.md prompt list and creates Google Calendar events
for each activity, so the user receives mobile notifications telling them
what to do and how.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.logging import log
from app.core.security import verify_auth
from app.services.google_calendar import get_google_calendar

router = APIRouter(prefix="/routine", dependencies=[Depends(verify_auth)])

ROUTINE_FILE = Path("./data/prompt-lists/rutina-diaria.md")


# =====================================================================
# MD parser — reads rutina-diaria.md into structured activities
# =====================================================================

def _parse_routine_md(path: Path) -> Dict[str, Any]:
    """
    Parse a routine markdown file into structured data.

    Expected format after the YAML frontmatter:
        ## activities
        - time: "HH:MM"
          duration: NN
          summary: "..."
          description: >
            multi-line text

    Returns dict with 'frontmatter' and 'activities' keys.
    """
    if not path.exists():
        raise FileNotFoundError(f"Routine file not found: {path}")

    raw = path.read_text(encoding="utf-8")

    # --- Split frontmatter from body ---
    frontmatter: Dict[str, Any] = {}
    body = raw
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1].strip()
            body = parts[2]
            for line in fm_text.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    val = val.strip().strip('"').strip("'")
                    # Handle YAML lists like [a, b, c]
                    if val.startswith("[") and val.endswith("]"):
                        val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",")]
                    elif val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    elif val.isdigit():
                        val = int(val)
                    frontmatter[key.strip()] = val

    # --- Parse activities block ---
    activities: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    collecting_desc = False
    desc_lines: List[str] = []

    for line in body.splitlines():
        stripped = line.strip()

        # New activity starts with "- time:"
        if stripped.startswith("- time:"):
            # Save previous activity
            if current is not None:
                if desc_lines:
                    current["description"] = "\n".join(desc_lines).strip()
                activities.append(current)

            time_val = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            # Handle "- time: "07:00"" format — the split above grabs everything
            # after first colon, e.g. ' "07:00"'. Clean it up.
            time_match = re.search(r'(\d{1,2}:\d{2})', time_val)
            current = {
                "time": time_match.group(1) if time_match else time_val,
                "duration": 30,
                "summary": "",
                "description": "",
            }
            collecting_desc = False
            desc_lines = []
            continue

        if current is None:
            continue

        # Duration line
        if stripped.startswith("duration:"):
            val = stripped.split(":", 1)[1].strip()
            current["duration"] = int(val) if val.isdigit() else 30
            collecting_desc = False

        # Summary line
        elif stripped.startswith("summary:"):
            current["summary"] = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            collecting_desc = False

        # Description start
        elif stripped.startswith("description:"):
            rest = stripped.split(":", 1)[1].strip()
            if rest and rest != ">":
                desc_lines.append(rest)
            collecting_desc = True

        # Continuation of multiline description
        elif collecting_desc and stripped:
            desc_lines.append(stripped)

        # Empty line in description — keep as paragraph break
        elif collecting_desc and not stripped:
            desc_lines.append("")

    # Save last activity
    if current is not None:
        if desc_lines:
            current["description"] = "\n".join(desc_lines).strip()
        activities.append(current)

    return {"frontmatter": frontmatter, "activities": activities}


def _compute_event_times(
    time_str: str,
    duration_min: int,
    target_date: str,
    tz_offset: str = "-06:00",
) -> tuple:
    """
    Compute ISO start/end datetimes for an activity.

    Args:
        time_str: "HH:MM"
        duration_min: duration in minutes
        target_date: "YYYY-MM-DD"
        tz_offset: timezone offset like "-06:00" (default: Mexico City CST)

    Returns:
        (start_iso, end_iso)
    """
    start_str = f"{target_date}T{time_str}:00{tz_offset}"
    start_dt = datetime.fromisoformat(start_str)
    end_dt = start_dt + timedelta(minutes=duration_min)
    return start_dt.isoformat(), end_dt.isoformat()


# Static fallback map (only used if zoneinfo cannot resolve the tz name)
_TZ_OFFSETS = {
    "America/Mexico_City": "-06:00",
    "America/Cancun": "-05:00",
    "America/Tijuana": "-08:00",
    "America/Hermosillo": "-07:00",
    "Europe/Madrid": "+02:00",
    "UTC": "+00:00",
}


def _tz_offset_for(tz_name: str, target_date: str) -> str:
    """
    Compute the UTC offset (e.g. "+02:00") for an IANA timezone on a given
    date, DST-aware via zoneinfo. Falls back to the static map, then UTC.

    Fixes the bug where any timezone missing from _TZ_OFFSETS (e.g.
    Europe/Madrid) silently fell back to Mexico City's -06:00.
    """
    try:
        tz = ZoneInfo(tz_name)
        dt = datetime.fromisoformat(f"{target_date}T12:00:00").replace(tzinfo=tz)
        offset = dt.utcoffset()
        if offset is None:
            raise ValueError("no utcoffset")
        total = int(offset.total_seconds())
        sign = "+" if total >= 0 else "-"
        total = abs(total)
        return f"{sign}{total // 3600:02d}:{(total % 3600) // 60:02d}"
    except Exception:
        return _TZ_OFFSETS.get(tz_name, "+00:00")


# =====================================================================
# Endpoints
# =====================================================================

class RoutineActivity(BaseModel):
    time: str
    duration: int
    summary: str
    description: str


class RoutineSyncResult(BaseModel):
    date: str
    events_created: int
    prompts_created: int
    activities: List[Dict[str, Any]]
    errors: List[str]


@router.get("/today")
async def get_today_routine():
    """
    Return today's routine activities parsed from rutina-diaria.md.
    Does NOT create calendar events — read-only preview.
    """
    try:
        data = _parse_routine_md(ROUTINE_FILE)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Routine file not found")
    except Exception as e:
        log.error(f"Failed to parse routine: {e}")
        raise HTTPException(status_code=500, detail=f"Parse error: {e}")

    today = datetime.now().strftime("%Y-%m-%d")
    tz_name = data["frontmatter"].get("timezone", "America/Mexico_City")
    tz_offset = _tz_offset_for(tz_name, today)

    enriched = []
    for act in data["activities"]:
        start_iso, end_iso = _compute_event_times(
            act["time"], act["duration"], today, tz_offset
        )
        enriched.append({
            **act,
            "start": start_iso,
            "end": end_iso,
        })

    return {
        "date": today,
        "timezone": tz_name,
        "activity_count": len(enriched),
        "activities": enriched,
    }


@router.post("/sync")
async def sync_routine_to_calendar(
    request: Request,
    date: Optional[str] = Query(
        default=None,
        description="Target date YYYY-MM-DD (default: today)",
    ),
    create_prompts: bool = Query(
        default=False,
        description="Also create prompts for each activity in the Prompt OS pipeline",
    ),
    calendar_id: str = Query(
        default="primary",
        description="Google Calendar ID to create events in",
    ),
):
    """
    Publish today's routine as Google Calendar events.

    Reads rutina-diaria.md, parses the 7 activities, and creates one
    calendar event per activity with the full description (what + how).
    Google Calendar then sends push notifications to the user's phone.
    """
    # Parse routine
    try:
        data = _parse_routine_md(ROUTINE_FILE)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Routine file not found")
    except Exception as e:
        log.error(f"Failed to parse routine: {e}")
        raise HTTPException(status_code=500, detail=f"Parse error: {e}")

    # Determine date and timezone
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    tz_name = data["frontmatter"].get("timezone", "America/Mexico_City")
    tz_offset = _tz_offset_for(tz_name, target_date)

    # Check Google Calendar connection
    gcal = get_google_calendar()
    if not gcal.is_connected():
        raise HTTPException(
            status_code=403,
            detail="Google Calendar not connected. Use /api/v1/calendar/auth first.",
        )

    events_created = 0
    prompts_created = 0
    errors: List[str] = []
    created_activities: List[Dict[str, Any]] = []

    for act in data["activities"]:
        start_iso, end_iso = _compute_event_times(
            act["time"], act["duration"], target_date, tz_offset
        )

        # Create Google Calendar event
        try:
            event = await gcal.create_event(
                calendar_id=calendar_id,
                summary=act["summary"],
                start=start_iso,
                end=end_iso,
                description=act["description"],
            )
            events_created += 1
            created_activities.append({
                **act,
                "start": start_iso,
                "end": end_iso,
                "calendar_event_id": event.get("id") if isinstance(event, dict) else None,
            })
            log.info(f"Created calendar event: {act['summary']} at {act['time']}")
        except Exception as e:
            error_msg = f"Failed to create event '{act['summary']}': {e}"
            log.error(error_msg)
            errors.append(error_msg)

        # Optionally create a prompt for each activity
        if create_prompts:
            try:
                prompt_store = getattr(request.app.state, "prompt_store", None)
                if prompt_store:
                    start_dt = datetime.fromisoformat(start_iso)
                    await prompt_store.create_prompt(
                        content=f"{act['summary']}: {act['description'][:200]}",
                        category="routine",
                        priority=5,
                        tags=["routine", "daily"],
                        scheduled_at=start_dt,
                        source="routine-sync",
                        status="pending",
                        workflow="quick_execute",
                        provider_policy="free-first",
                    )
                    prompts_created += 1
            except Exception as e:
                errors.append(f"Failed to create prompt for '{act['summary']}': {e}")

    log.info(
        f"Routine sync complete: {events_created} events, "
        f"{prompts_created} prompts, {len(errors)} errors"
    )

    return RoutineSyncResult(
        date=target_date,
        events_created=events_created,
        prompts_created=prompts_created,
        activities=created_activities,
        errors=errors,
    )
