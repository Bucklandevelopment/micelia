"""
Sync API: endpoints para sincronizacion bidireccional DB <-> Markdown.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from app.core.logging import log
from app.core.security import verify_auth

router = APIRouter(prefix="/sync", dependencies=[Depends(verify_auth)])


@router.get("/status")
async def sync_status(request: Request):
    """
    Returns sync service status and last run timestamp.
    """
    md_sync = getattr(request.app.state, "md_sync", None)
    if not md_sync:
        return {
            "status": "disabled",
            "message": "MarkdownSyncService not initialized",
        }

    return md_sync.get_status()


@router.post("/run")
async def sync_run(request: Request):
    """
    Triggers a manual full sync (MD <-> DB) immediately.
    """
    md_sync = getattr(request.app.state, "md_sync", None)
    if not md_sync:
        return {
            "status": "error",
            "message": "MarkdownSyncService not initialized",
        }

    log.info("Manual sync triggered via API")
    result = await md_sync.full_sync()

    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }


@router.get("/inbox")
async def sync_inbox(request: Request):
    """
    Returns today's inbox markdown content.
    """
    md_sync = getattr(request.app.state, "md_sync", None)
    if not md_sync:
        return PlainTextResponse(
            content="# MarkdownSyncService not initialized\n",
            status_code=503,
        )

    content = await md_sync.get_today_inbox_md()
    if not content:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        content = f"# Inbox {today}\n\n_No captured prompts today._\n"

    return PlainTextResponse(content=content, media_type="text/markdown")
