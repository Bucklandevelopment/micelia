"""
Health checks y status del sistema.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/health")


class ServiceStatus(BaseModel):
    name: str
    url: str
    enabled: bool
    healthy: bool
    latency_ms: float | None = None
    error: str | None = None
    # Versión reportada por el dominio en el body de su health-check. La
    # registra `ServiceRegistry._check_health` (`data.get("version")`) y aquí se
    # propaga al consumidor. Contrato auditado (Ciclo 42): biohack
    # (/api/v1/service-health), ideacursi (/api/health) y cybertools (/health)
    # devuelven `version` a nivel superior; canela (/health) NO lo emite → queda
    # None (lectura defensiva, sin romper). Ver DP-8 en el ITERATION_LOG.
    version: str | None = None


class SystemHealth(BaseModel):
    status: str  # healthy, degraded, unhealthy
    timestamp: str
    uptime_seconds: float
    services: Dict[str, ServiceStatus]
    resources: Dict[str, Any]


# Track startup time
_startup_time = datetime.now(timezone.utc)


@router.get("")
async def health_check():
    """Health check básico para load balancers"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/ready")
async def readiness_check(request: Request):
    """
    Readiness check: verifica que el sistema esté listo para recibir tráfico.
    """
    registry = request.app.state.service_registry

    # Verificar al menos un servicio crítico
    health_status = await registry.check_service("health")
    research_status = await registry.check_service("research")

    if health_status.healthy or research_status.healthy:
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}

    return {"status": "not_ready", "reason": "No critical services available"}


@router.get("/live")
async def liveness_check():
    """Liveness check: verifica que el proceso esté vivo"""
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/detailed", response_model=SystemHealth)
async def detailed_health(request: Request):
    """
    Health check detallado con estado de todos los servicios y recursos.
    """
    registry = request.app.state.service_registry

    # Verificar todos los servicios
    services = {}
    all_healthy = True
    any_healthy = False

    for service_name in ["health", "research", "education", "security"]:
        status = await registry.check_service(service_name)
        services[service_name] = status
        if status.healthy:
            any_healthy = True
        else:
            all_healthy = False

    # Determinar estado general
    if all_healthy:
        overall_status = "healthy"
    elif any_healthy:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    # Recursos del sistema
    import psutil
    resources = {
        "cpu_percent": psutil.cpu_percent(),
        "memory": {
            "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "percent": psutil.virtual_memory().percent
        },
        "disk": {
            "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
            "free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
            "percent": psutil.disk_usage('/').percent
        }
    }

    uptime = (datetime.now(timezone.utc) - _startup_time).total_seconds()

    return SystemHealth(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=uptime,
        services=services,
        resources=resources
    )


@router.get("/services")
async def services_status(request: Request):
    """Estado de todos los microservicios conectados"""
    registry = request.app.state.service_registry

    results = {}
    for service_name in ["health", "research", "education", "security"]:
        status = await registry.check_service(service_name)
        results[service_name] = {
            "name": status.name,
            "url": status.url,
            "enabled": status.enabled,
            "healthy": status.healthy,
            "latency_ms": status.latency_ms,
            "error": status.error,
            "version": status.version
        }

    return {"services": results}
