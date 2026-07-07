"""
Tunnel Service: Gestión programática de tunnels ngrok.

Expone Micelia al mundo via URL pública.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import settings
from app.core.logging import log


class TunnelService:
    """
    Gestiona tunnels ngrok para exposición pública de Micelia.
    """

    def __init__(self):
        self._tunnel: Any = None
        self._public_url: Optional[str] = None
        self._started_at: Optional[str] = None
        self._connected = False

    async def start(self, port: Optional[int] = None) -> Optional[str]:
        """Inicia un tunnel ngrok y retorna la URL pública."""
        if self._connected:
            return self._public_url

        port = port or settings.gateway_port

        try:
            from pyngrok import conf, ngrok

            if settings.ngrok_authtoken:
                conf.get_default().auth_token = settings.ngrok_authtoken

            options: Dict[str, Any] = {"addr": port, "bind_tls": True}

            if settings.ngrok_domain:
                options["hostname"] = settings.ngrok_domain

            self._tunnel = ngrok.connect(**options)
            self._public_url = self._tunnel.public_url
            self._started_at = datetime.now(timezone.utc).isoformat()
            self._connected = True

            log.info(f"ngrok tunnel started: {self._public_url} -> localhost:{port}")
            return self._public_url

        except ImportError:
            log.error("pyngrok not installed. Run: pip install pyngrok")
            return None
        except Exception as e:
            log.error(f"Failed to start ngrok tunnel: {e}")
            self._connected = False
            return None

    async def stop(self):
        """Detiene el tunnel ngrok."""
        if not self._connected:
            return

        try:
            from pyngrok import ngrok
            ngrok.disconnect(self._tunnel.public_url)
            ngrok.kill()
            self._connected = False
            self._public_url = None
            self._tunnel = None
            self._started_at = None
            log.info("ngrok tunnel stopped")
        except Exception as e:
            log.error(f"Failed to stop ngrok tunnel: {e}")

    def get_info(self) -> Dict:
        """Retorna información del tunnel activo."""
        if not self._connected:
            return {
                "connected": False,
                "public_url": None,
                "started_at": None,
            }

        info: Dict[str, Any] = {
            "connected": True,
            "public_url": self._public_url,
            "started_at": self._started_at,
        }

        try:
            from pyngrok import ngrok
            tunnels = ngrok.get_tunnels()
            info["tunnels_count"] = len(tunnels)
            if tunnels:
                t = tunnels[0]
                info["proto"] = t.proto
                info["config"] = {"addr": t.config.get("addr", "")} if hasattr(t, "config") else {}
        except Exception:
            pass

        return info

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def public_url(self) -> Optional[str]:
        return self._public_url


# Singleton
_tunnel_service: Optional[TunnelService] = None


def get_tunnel_service() -> TunnelService:
    global _tunnel_service
    if _tunnel_service is None:
        _tunnel_service = TunnelService()
    return _tunnel_service
