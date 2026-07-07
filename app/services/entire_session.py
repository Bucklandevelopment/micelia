"""
Entire CLI integration for agent session traceability.

Wraps the `entire` CLI (https://github.com/entireio/cli) for
capturing agent sessions, checkpoints, and audit trails.

Gracefully degrades to in-memory-only tracking when entire is not installed.
"""

import asyncio
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.logging import log


class EntireSessionService:
    def __init__(self):
        self._entire_available: Optional[bool] = None
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._max_stored = 500

    @property
    def is_available(self) -> bool:
        if self._entire_available is None:
            self._entire_available = shutil.which("entire") is not None
            if not self._entire_available:
                log.info("entire CLI not found — audit sessions tracked in-memory only")
            else:
                log.info("entire CLI found — full session traceability enabled")
        return self._entire_available

    async def start_session(
        self,
        prompt_id: str,
        workflow_name: Optional[str] = None,
        run_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = str(uuid4())
        session: Dict[str, Any] = {
            "session_id": session_id,
            "prompt_id": prompt_id,
            "workflow_name": workflow_name,
            "run_id": run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "checkpoints": [],
            "status": "active",
            "metadata": metadata or {},
            "entire_session_id": None,
        }

        if self.is_available:
            try:
                result = await self._run_entire(
                    "session", "start",
                    "--name", f"idm-{prompt_id[:8]}",
                )
                session["entire_session_id"] = result.strip()
            except Exception as e:
                log.warning(f"entire session start failed: {e}")

        self._sessions[session_id] = session
        self._trim_sessions()
        return session_id

    async def checkpoint(
        self,
        session_id: str,
        agent_name: str,
        action: str,
        output_summary: Optional[str] = None,
    ) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return

        cp = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "action": action,
            "output_summary": output_summary[:500] if output_summary else None,
        }
        session["checkpoints"].append(cp)

        if self.is_available and session.get("entire_session_id"):
            try:
                await self._run_entire(
                    "checkpoint", "create",
                    "--message", f"{agent_name}:{action}",
                )
            except Exception as e:
                log.debug(f"entire checkpoint failed: {e}")

    async def end_session(self, session_id: str, status: str = "completed") -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        session["status"] = status
        session["ended_at"] = datetime.now(timezone.utc).isoformat()

        if self.is_available and session.get("entire_session_id"):
            try:
                await self._run_entire("session", "end")
            except Exception as e:
                log.debug(f"entire session end failed: {e}")

    def get_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        sessions = sorted(
            self._sessions.values(),
            key=lambda s: s.get("started_at", ""),
            reverse=True,
        )
        return sessions[offset:offset + limit]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._sessions.get(session_id)

    def get_sessions_for_prompt(self, prompt_id: str) -> List[Dict[str, Any]]:
        return sorted(
            [s for s in self._sessions.values() if s.get("prompt_id") == prompt_id],
            key=lambda s: s.get("started_at", ""),
            reverse=True,
        )

    def get_status(self) -> Dict[str, Any]:
        active = sum(1 for s in self._sessions.values() if s["status"] == "active")
        return {
            "entire_available": self.is_available,
            "total_sessions": len(self._sessions),
            "active_sessions": active,
        }

    async def _run_entire(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "entire", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
        if proc.returncode != 0:
            raise RuntimeError(f"entire failed: {stderr.decode().strip()}")
        return stdout.decode()

    def _trim_sessions(self) -> None:
        if len(self._sessions) > self._max_stored:
            sorted_keys = sorted(
                self._sessions.keys(),
                key=lambda k: self._sessions[k].get("started_at", ""),
            )
            for key in sorted_keys[:len(self._sessions) - self._max_stored]:
                del self._sessions[key]


_entire_service: Optional[EntireSessionService] = None

def get_entire_service() -> EntireSessionService:
    global _entire_service
    if _entire_service is None:
        _entire_service = EntireSessionService()
    return _entire_service
