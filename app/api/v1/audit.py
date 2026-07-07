"""
Audit API: endpoints for session traceability and workflow audit trails.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import verify_auth
from app.services.entire_session import get_entire_service

router = APIRouter(prefix="/audit", dependencies=[Depends(verify_auth)])


@router.get("/status")
async def audit_status():
    service = get_entire_service()
    return service.get_status()


@router.get("/sessions")
async def list_sessions(limit: int = 50, offset: int = 0):
    service = get_entire_service()
    sessions = service.get_sessions(limit=limit, offset=offset)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    service = get_entire_service()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/prompts/{prompt_id}/sessions")
async def get_prompt_sessions(prompt_id: str):
    service = get_entire_service()
    sessions = service.get_sessions_for_prompt(prompt_id)
    return {"prompt_id": prompt_id, "sessions": sessions}
