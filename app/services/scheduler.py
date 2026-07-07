"""
Prompt Scheduler: Background task for scheduled prompt execution.

Runs every 60 seconds to:
1. Move scheduled prompts from pending → queued when their time arrives
2. Sync prompts from Google Calendar (if connected)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.logging import log
from app.core.time import utcnow_naive


class PromptScheduler:
    """
    Background scheduler that processes time-based prompt triggers.

    Follows the start/stop pattern of PromptPrioritizationAgent.
    Scans every 60 seconds for:
    - Prompts with scheduled_at in the next minute → moves to queued
    - Google Calendar events tagged [PROMPT] → creates prompts
    """

    def __init__(self, prompt_store=None, event_bus=None):
        self._store = prompt_store
        self._event_bus = event_bus
        self._task: Optional[asyncio.Task] = None
        self.interval = settings.google_calendar_sync_interval  # 60s default
        self.running = False
        self.last_scan: Optional[datetime] = None
        self.synced_count: int = 0
        self._scheduled_moved: int = 0

    async def start(self):
        """Start the scheduler background loop."""
        if self._task and not self._task.done():
            return

        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        log.info(f"PromptScheduler started (interval: {self.interval}s)")

    async def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("PromptScheduler stopped")

    async def _run_loop(self):
        """Main loop: scan scheduled prompts + calendar sync."""
        while self.running:
            try:
                await self._process_scheduled()
                await self._sync_calendar()
                self.last_scan = utcnow_naive()
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"PromptScheduler error: {e}")
                await asyncio.sleep(self.interval)

    async def _process_scheduled(self):
        """
        Find prompts with scheduled_at in the next minute and move them to queued.
        """
        if not self._store:
            return

        try:
            now = utcnow_naive()
            cutoff = now + timedelta(seconds=60)

            scheduled = await self._store.get_scheduled_prompts(before=cutoff)

            if not scheduled:
                return

            moved = 0
            for prompt in scheduled:
                await self._store.update_prompt(
                    prompt["prompt_id"],
                    status="queued",
                )
                moved += 1

                # Publish event if event bus is available
                if self._event_bus:
                    try:
                        await self._event_bus.publish("idm.prompts", {
                            "type": "prompt.scheduled_triggered",
                            "prompt_id": prompt["prompt_id"],
                            "category": prompt.get("category", ""),
                            "scheduled_at": prompt.get("scheduled_at", ""),
                        })
                    except Exception:
                        pass  # Event bus may not be available

            if moved:
                self._scheduled_moved += moved
                log.info(f"PromptScheduler: moved {moved} scheduled prompts to queued")

        except Exception as e:
            log.error(f"PromptScheduler scheduled processing error: {e}")

    async def _sync_calendar(self):
        """
        If Google Calendar is connected, sync prompts from calendar events.
        """
        if not settings.google_calendar_enabled:
            return

        try:
            from app.services.google_calendar import get_google_calendar

            gcal = get_google_calendar()
            if not gcal.is_connected():
                return

            result = await gcal.sync_prompts_from_calendar()
            synced = result.get("synced", 0)

            if synced > 0:
                self.synced_count += synced
                log.info(f"PromptScheduler: synced {synced} prompts from Google Calendar")

        except ImportError:
            log.debug("Google Calendar service not available for sync")
        except Exception as e:
            log.error(f"PromptScheduler calendar sync error: {e}")

    def get_status(self) -> dict:
        """Returns scheduler status info."""
        return {
            "running": self.running,
            "interval_seconds": self.interval,
            "last_scan": self.last_scan.isoformat() if self.last_scan else None,
            "total_scheduled_moved": self._scheduled_moved,
            "total_calendar_synced": self.synced_count,
            "calendar_enabled": settings.google_calendar_enabled,
        }


# ==================== SINGLETON ====================

_scheduler: Optional[PromptScheduler] = None


def get_scheduler() -> PromptScheduler:
    """Singleton accessor for PromptScheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = PromptScheduler()
    return _scheduler
