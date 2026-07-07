"""
API Tunnel: ngrok tunnel management.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import verify_auth
from app.services.tunnel import get_tunnel_service

router = APIRouter(prefix="/tunnel", dependencies=[Depends(verify_auth)])


class TunnelStartRequest(BaseModel):
    port: Optional[int] = None


@router.get("/status")
async def tunnel_status():
    """URL pública actual y estado del tunnel."""
    service = get_tunnel_service()
    return service.get_info()


@router.post("/start")
async def tunnel_start(request: TunnelStartRequest = None):
    """Inicia un tunnel ngrok."""
    service = get_tunnel_service()

    if service.is_connected:
        return {
            "success": True,
            "message": "Tunnel already running",
            "public_url": service.public_url,
        }

    port = request.port if request else None
    url = await service.start(port)

    if url:
        return {"success": True, "public_url": url}
    else:
        raise HTTPException(status_code=500, detail="Failed to start tunnel. Check ngrok configuration.")


@router.post("/stop")
async def tunnel_stop():
    """Detiene el tunnel ngrok."""
    service = get_tunnel_service()

    if not service.is_connected:
        return {"success": True, "message": "No tunnel running"}

    await service.stop()
    return {"success": True, "message": "Tunnel stopped"}


@router.get("/info")
async def tunnel_info():
    """Métricas detalladas del tunnel."""
    service = get_tunnel_service()
    return service.get_info()
