"""
Google Calendar Service: OAuth2 integration for calendar sync.

Enables bi-directional sync between Micelia prompts and Google Calendar:
- Read calendar events tagged [PROMPT] → create prompts
- Write completed prompt results → calendar events
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logging import log

# Google API packages are optional
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False
    Credentials = None
    Flow = None
    build = None


TOKEN_PATH = Path("./data/google_token.json")
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
REDIRECT_URI = "http://localhost:8888/api/v1/calendar/callback"


class GoogleCalendarService:
    """
    Google Calendar integration via OAuth2.

    Handles authentication, event CRUD, and bi-directional
    sync with the Micelia prompt system.
    """

    def __init__(self):
        self._credentials: Optional[Any] = None
        self._service: Optional[Any] = None
        self._last_sync: Optional[datetime] = None
        self._synced_event_ids: set = set()

    # ==================== AUTH ====================

    async def authenticate(self) -> Dict[str, Any]:
        """
        Generates an OAuth2 authorization URL for the user to visit.

        Returns:
            dict with authorization_url and state
        """
        if not GOOGLE_LIBS_AVAILABLE:
            raise RuntimeError(
                "Google API libraries not installed. "
                "Run: pip install google-auth-oauthlib google-api-python-client"
            )

        if not settings.google_client_id or not settings.google_client_secret:
            raise ValueError(
                "Google Calendar credentials not configured. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
            )

        try:
            client_config = {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            }

            flow = Flow.from_client_config(client_config, scopes=SCOPES)
            flow.redirect_uri = REDIRECT_URI

            authorization_url, state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )

            log.info("Google Calendar OAuth2 URL generated")
            return {
                "authorization_url": authorization_url,
                "state": state,
            }

        except Exception as e:
            log.error(f"Google Calendar auth error: {e}")
            raise

    async def handle_callback(self, code: str) -> Dict[str, Any]:
        """
        Handles OAuth2 callback, exchanges code for tokens and saves them.

        Args:
            code: Authorization code from Google OAuth2 callback

        Returns:
            dict with success status and user email
        """
        if not GOOGLE_LIBS_AVAILABLE:
            raise RuntimeError("Google API libraries not installed")

        try:
            client_config = {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [REDIRECT_URI],
                }
            }

            flow = Flow.from_client_config(client_config, scopes=SCOPES)
            flow.redirect_uri = REDIRECT_URI
            flow.fetch_token(code=code)

            credentials = flow.credentials
            self._credentials = credentials

            # Save token to disk
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            }
            TOKEN_PATH.write_text(json.dumps(token_data, indent=2))

            # Build service
            self._service = build("calendar", "v3", credentials=credentials)

            log.info("Google Calendar connected successfully")
            return {"success": True, "message": "Google Calendar connected"}

        except Exception as e:
            log.error(f"Google Calendar callback error: {e}")
            raise

    def is_connected(self) -> bool:
        """Check if Google Calendar token exists and credentials are loaded."""
        if self._credentials is not None:
            return True

        if not TOKEN_PATH.exists():
            return False

        # Try to load saved token
        try:
            self._load_credentials()
            return self._credentials is not None
        except Exception:
            return False

    def _load_credentials(self):
        """Load credentials from saved token file."""
        if not GOOGLE_LIBS_AVAILABLE:
            return

        if not TOKEN_PATH.exists():
            return

        try:
            token_data = json.loads(TOKEN_PATH.read_text())
            self._credentials = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes", SCOPES),
            )

            # Check if token needs refresh
            if self._credentials.expired and self._credentials.refresh_token:
                from google.auth.transport.requests import Request
                self._credentials.refresh(Request())
                # Save refreshed token
                self._save_credentials()

            self._service = build("calendar", "v3", credentials=self._credentials)
            log.debug("Google Calendar credentials loaded from token file")

        except Exception as e:
            log.error(f"Failed to load Google Calendar credentials: {e}")
            self._credentials = None
            self._service = None

    def _save_credentials(self):
        """Save current credentials to token file."""
        if not self._credentials:
            return

        try:
            token_data = {
                "token": self._credentials.token,
                "refresh_token": self._credentials.refresh_token,
                "token_uri": self._credentials.token_uri,
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
                "scopes": list(self._credentials.scopes) if self._credentials.scopes else SCOPES,
                "expiry": self._credentials.expiry.isoformat() if self._credentials.expiry else None,
            }
            TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
        except Exception as e:
            log.error(f"Failed to save credentials: {e}")

    def _ensure_service(self):
        """Ensure the Google Calendar API service is initialized."""
        if self._service is not None:
            return

        if not self.is_connected():
            raise RuntimeError("Google Calendar not connected. Call authenticate() first.")

    # ==================== CALENDARS ====================

    async def list_calendars(self) -> List[Dict[str, Any]]:
        """
        Returns list of user's calendars.

        Returns:
            List of calendar dicts with id, summary, primary flag
        """
        self._ensure_service()

        try:
            result = await asyncio.to_thread(
                self._service.calendarList().list().execute
            )

            calendars = []
            for cal in result.get("items", []):
                calendars.append({
                    "id": cal["id"],
                    "summary": cal.get("summary", ""),
                    "description": cal.get("description", ""),
                    "primary": cal.get("primary", False),
                    "time_zone": cal.get("timeZone", ""),
                    "background_color": cal.get("backgroundColor", ""),
                    "access_role": cal.get("accessRole", ""),
                })

            log.debug(f"Listed {len(calendars)} calendars")
            return calendars

        except Exception as e:
            log.error(f"Failed to list calendars: {e}")
            raise

    # ==================== EVENTS ====================

    async def get_events(
        self,
        calendar_id: str = "primary",
        time_min: str = None,
        time_max: str = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get events from a calendar within a date range.

        Args:
            calendar_id: Calendar ID (default: "primary")
            time_min: ISO format start time (default: now)
            time_max: ISO format end time (default: 7 days from now)
            max_results: Maximum number of events

        Returns:
            List of event dicts
        """
        self._ensure_service()

        now = datetime.now(timezone.utc)
        if not time_min:
            time_min = now.isoformat()
        if not time_max:
            time_max = (now + timedelta(days=7)).isoformat()

        try:
            result = await asyncio.to_thread(
                self._service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute
            )

            events = []
            for event in result.get("items", []):
                start = event.get("start", {})
                end = event.get("end", {})
                events.append({
                    "id": event["id"],
                    "summary": event.get("summary", ""),
                    "description": event.get("description", ""),
                    "start": start.get("dateTime", start.get("date", "")),
                    "end": end.get("dateTime", end.get("date", "")),
                    "status": event.get("status", ""),
                    "html_link": event.get("htmlLink", ""),
                    "created": event.get("created", ""),
                    "updated": event.get("updated", ""),
                })

            log.debug(f"Retrieved {len(events)} events from {calendar_id}")
            return events

        except Exception as e:
            log.error(f"Failed to get events: {e}")
            raise

    async def create_event(
        self,
        calendar_id: str = "primary",
        summary: str = "",
        start: str = "",
        end: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Create a new calendar event.

        Args:
            calendar_id: Calendar ID
            summary: Event title
            start: ISO format start time
            end: ISO format end time
            description: Event description

        Returns:
            Created event dict with id and html_link
        """
        self._ensure_service()

        if not summary:
            raise ValueError("Event summary is required")
        if not start or not end:
            raise ValueError("Event start and end times are required")

        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }

        try:
            result = await asyncio.to_thread(
                self._service.events()
                .insert(calendarId=calendar_id, body=event_body)
                .execute
            )

            log.info(f"Created calendar event: {summary}")
            return {
                "id": result["id"],
                "summary": result.get("summary", ""),
                "start": result.get("start", {}).get("dateTime", ""),
                "end": result.get("end", {}).get("dateTime", ""),
                "html_link": result.get("htmlLink", ""),
                "status": result.get("status", ""),
            }

        except Exception as e:
            log.error(f"Failed to create event: {e}")
            raise

    # ==================== SYNC ====================

    async def sync_prompts_from_calendar(self) -> Dict[str, Any]:
        """
        Reads events with [PROMPT] in summary and creates prompts via PromptStore.

        Scans the next 24 hours for events whose summary contains [PROMPT].
        Creates a prompt for each, setting scheduled_at to the event start time.

        Returns:
            dict with created count and prompt IDs
        """
        self._ensure_service()

        try:
            # Import here to avoid circular imports
            from app.services.prompt_store import get_prompt_store

            store = get_prompt_store()

            now = datetime.now(timezone.utc)
            time_max = (now + timedelta(days=1)).isoformat()

            events = await self.get_events(
                calendar_id="primary",
                time_min=now.isoformat(),
                time_max=time_max,
            )

            created_ids = []
            for event in events:
                summary = event.get("summary", "")
                if "[PROMPT]" not in summary:
                    continue

                # Skip already synced events
                event_id = event.get("id", "")
                if event_id in self._synced_event_ids:
                    continue

                # Extract prompt content: remove [PROMPT] tag
                content = summary.replace("[PROMPT]", "").strip()
                if not content:
                    content = event.get("description", "No content")

                # Parse scheduled time
                start_str = event.get("start", "")
                scheduled_at = None
                if start_str:
                    try:
                        scheduled_at = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        scheduled_at = None

                prompt_id = await store.create_prompt(
                    content=content,
                    category="work",
                    priority=7,
                    tags=["calendar-sync", "scheduled"],
                    scheduled_at=scheduled_at,
                    source="google-calendar",
                    metadata={"calendar_event_id": event_id},
                )

                created_ids.append(str(prompt_id))
                self._synced_event_ids.add(event_id)

            self._last_sync = now

            if created_ids:
                log.info(f"Calendar sync: created {len(created_ids)} prompts from events")

            return {
                "synced": len(created_ids),
                "prompt_ids": created_ids,
                "sync_time": now.isoformat(),
            }

        except Exception as e:
            log.error(f"Calendar sync (from) error: {e}")
            raise

    async def sync_results_to_calendar(self) -> Dict[str, Any]:
        """
        Creates calendar events with results of completed prompts.

        Finds prompts sourced from google-calendar that have completed,
        and writes a result event back to the calendar.

        Returns:
            dict with synced count and event IDs
        """
        self._ensure_service()

        try:
            from app.services.prompt_store import get_prompt_store

            store = get_prompt_store()

            # Get recently completed prompts from calendar source
            result = await store.list_prompts(
                status="completed",
                source="google-calendar",
                limit=20,
            )

            created_events = []
            for prompt in result.get("prompts", []):
                # Skip if no output
                if not prompt.get("output"):
                    continue

                # Skip if already synced back (check metadata)
                metadata = prompt.get("metadata", {})
                if metadata.get("synced_to_calendar"):
                    continue

                completed_at = prompt.get("completed_at", "")
                if not completed_at:
                    continue

                try:
                    end_time = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    end_time = datetime.now(timezone.utc)

                start_time = end_time
                end_time_plus = end_time + timedelta(minutes=15)

                summary = f"[RESULT] {prompt.get('content', 'Prompt')[:80]}"
                description = (
                    f"Prompt ID: {prompt['prompt_id']}\n"
                    f"Category: {prompt.get('category', 'N/A')}\n"
                    f"Model: {prompt.get('model_used', 'N/A')}\n\n"
                    f"--- Output ---\n{prompt.get('output', '')[:500]}"
                )

                event = await self.create_event(
                    calendar_id="primary",
                    summary=summary,
                    start=start_time.isoformat(),
                    end=end_time_plus.isoformat(),
                    description=description,
                )

                # Mark prompt as synced back
                await store.update_prompt(
                    prompt["prompt_id"],
                    metadata_json={**metadata, "synced_to_calendar": True},
                )

                created_events.append(event.get("id", ""))

            if created_events:
                log.info(f"Calendar sync: created {len(created_events)} result events")

            return {
                "synced": len(created_events),
                "event_ids": created_events,
            }

        except Exception as e:
            log.error(f"Calendar sync (to) error: {e}")
            raise

    # ==================== DISCONNECT ====================

    async def disconnect(self) -> Dict[str, Any]:
        """
        Removes the token file and clears credentials.

        Returns:
            dict with success status
        """
        try:
            if TOKEN_PATH.exists():
                TOKEN_PATH.unlink()

            self._credentials = None
            self._service = None
            self._synced_event_ids.clear()
            self._last_sync = None

            log.info("Google Calendar disconnected")
            return {"success": True, "message": "Google Calendar disconnected"}

        except Exception as e:
            log.error(f"Failed to disconnect Google Calendar: {e}")
            raise

    # ==================== STATUS ====================

    def get_status(self) -> Dict[str, Any]:
        """Returns current connection status and sync info."""
        connected = self.is_connected()
        return {
            "connected": connected,
            "enabled": settings.google_calendar_enabled,
            "google_libs_available": GOOGLE_LIBS_AVAILABLE,
            "token_exists": TOKEN_PATH.exists(),
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "synced_events_count": len(self._synced_event_ids),
        }


# ==================== SINGLETON ====================

_google_calendar: Optional[GoogleCalendarService] = None


def get_google_calendar() -> GoogleCalendarService:
    """Singleton accessor for GoogleCalendarService."""
    global _google_calendar
    if _google_calendar is None:
        _google_calendar = GoogleCalendarService()
    return _google_calendar
