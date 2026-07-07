"""
Service Registry: Descubrimiento y monitoreo de microservicios.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

import httpx

from app.api.v1.health import ServiceStatus
from app.core.config import settings
from app.core.logging import log


@dataclass
class ServiceInfo:
    """Información de un servicio registrado"""
    name: str
    url: str
    enabled: bool
    healthy: bool = False
    last_check: Optional[datetime] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    version: Optional[str] = None


class ServiceRegistry:
    """
    Registry de servicios que mantiene estado de health de cada microservicio.
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.client = http_client
        self.services: Dict[str, ServiceInfo] = {}
        self._check_interval = settings.health_check_interval
        self._monitoring_task: Optional[asyncio.Task] = None

    async def discover_services(self):
        """Descubre y registra todos los servicios configurados"""

        service_configs = {
            "health": {
                "url": settings.health_service_url,
                "enabled": settings.health_service_enabled,
                "health_endpoint": "/api/v1/service-health"
            },
            "research": {
                "url": settings.research_service_url,
                "enabled": settings.research_service_enabled,
                "health_endpoint": "/health"
            },
            "education": {
                "url": settings.education_service_url,
                "enabled": settings.education_service_enabled,
                "health_endpoint": "/api/health"
            },
            "security": {
                "url": settings.security_service_url,
                "enabled": settings.security_service_enabled,
                "health_endpoint": "/health"
            },
            # DevTools Services
            "devtools": {
                "url": settings.ollama_code_url,
                "enabled": settings.ollama_code_enabled,
                "health_endpoint": "/health"
            },
            "testlab": {
                "url": settings.imperio_lab_url,
                "enabled": settings.imperio_lab_enabled,
                "health_endpoint": "/health"
            }
        }

        for name, config in service_configs.items():
            self.services[name] = ServiceInfo(
                name=name,
                url=config["url"],
                enabled=config["enabled"]
            )

            if config["enabled"]:
                # log_on_fail=False: silenciamos los warnings individuales del
                # arranque; abajo emitimos UN resumen consolidado.
                await self._check_health(
                    name, config["health_endpoint"], log_on_fail=False
                )

        # Iniciar monitoreo continuo
        self._monitoring_task = asyncio.create_task(self._continuous_monitoring())

        # Resumen consolidado del estado inicial
        enabled = [s for s in self.services.values() if s.enabled]
        healthy = [s for s in enabled if s.healthy]
        unhealthy = [s for s in enabled if not s.healthy]
        log.info(
            f"Service Registry: {len(self.services)} servicios registrados "
            f"({len(healthy)}/{len(enabled)} healthy)"
        )
        if unhealthy:
            names = ", ".join(s.name for s in unhealthy)
            # Mapeo dominio → target Makefile mínimo que lo levanta.
            # Si SOLO falta 'health' (biohack), basta con `make docker-health`.
            # Si falta cualquier otro, recomendamos `make docker-full`.
            unhealthy_names = {s.name for s in unhealthy}
            if unhealthy_names == {"health"}:
                hint = "make docker-health"
            else:
                hint = "make docker-full"
            log.warning(
                f"Subservicios opcionales sin conexión: {names}. "
                f"Para levantarlos: {hint}. "
                f"Reintentos cada {self._check_interval}s en background."
            )

    async def _check_health(
        self,
        service_name: str,
        health_endpoint: str,
        *,
        log_on_fail: bool = True,
    ) -> bool:
        """Verifica health de un servicio.

        `log_on_fail`:
          - True (default): emite WARNING al fallar SOLO si era el primer fallo
            tras estar healthy (transición healthy→unhealthy). Si ya estaba
            caído, lo loguea como DEBUG para no spamear.
          - False: silencia el log; útil para el arranque consolidado.
        """
        service = self.services.get(service_name)
        if not service:
            return False

        was_healthy = service.healthy

        try:
            start = datetime.now(timezone.utc)

            response = await self.client.get(
                f"{service.url}{health_endpoint}",
                timeout=settings.service_timeout
            )

            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            service.healthy = response.status_code == 200
            service.latency_ms = round(latency, 2)
            service.last_check = datetime.now(timezone.utc)
            service.error = None

            # Intentar obtener versión
            if response.status_code == 200:
                try:
                    data = response.json()
                    service.version = data.get("version")
                except Exception:
                    pass

            # Recuperación: si estaba caído y ahora responde, lo notificamos.
            if service.healthy and not was_healthy and log_on_fail:
                log.info(
                    f"Service '{service_name}' recovered ({latency:.0f}ms)"
                )
            else:
                log.debug(f"Health check {service_name}: OK ({latency:.0f}ms)")
            return True

        except httpx.TimeoutException:
            service.healthy = False
            service.error = "timeout"
            service.last_check = datetime.now(timezone.utc)
            self._log_failure(service_name, "timeout", was_healthy, log_on_fail)
            return False

        except httpx.ConnectError:
            service.healthy = False
            service.error = "connection_refused"
            service.last_check = datetime.now(timezone.utc)
            self._log_failure(
                service_name, "connection refused", was_healthy, log_on_fail
            )
            return False

        except Exception as e:
            service.healthy = False
            service.error = str(e)
            service.last_check = datetime.now(timezone.utc)
            log.error(f"Health check {service_name}: {e}")
            return False

    @staticmethod
    def _log_failure(
        service_name: str,
        reason: str,
        was_healthy: bool,
        log_on_fail: bool,
    ) -> None:
        """Decide el nivel del log según el contexto del fallo.

        - WARNING: transición healthy → unhealthy (algo importante cambió).
        - DEBUG: el servicio ya estaba caído desde antes (ruido repetitivo).
        - Silenciado: `log_on_fail=False` (usado en discover_services para
          consolidar en un único resumen).
        """
        if not log_on_fail:
            log.debug(f"Health check {service_name}: {reason}")
            return
        if was_healthy:
            log.warning(
                f"Service '{service_name}' became unreachable: {reason}"
            )
        else:
            log.debug(
                f"Health check {service_name}: {reason} (still down)"
            )

    async def _continuous_monitoring(self):
        """Monitoreo continuo de todos los servicios.

        Espera `_check_interval` segundos ANTES del primer ciclo para no
        duplicar el chequeo inicial que ya hizo `discover_services`.
        """
        health_endpoints = {
            "health": "/api/v1/service-health",
            "research": "/health",
            "education": "/api/health",
            "security": "/health",
            "devtools": "/health",
            "testlab": "/health"
        }

        while True:
            try:
                # Esperar primero — evita re-chequear inmediatamente lo que
                # discover_services acaba de chequear.
                await asyncio.sleep(self._check_interval)

                for name, service in self.services.items():
                    if service.enabled:
                        # log_on_fail=True para detectar transiciones (un
                        # servicio que cae después de estar healthy). Los que
                        # llevan caídos desde el arranque se silencian dentro
                        # de _check_health (se logean como DEBUG).
                        await self._check_health(name, health_endpoints[name])

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)

    async def check_service(self, service_name: str) -> ServiceStatus:
        """Obtiene estado actual de un servicio"""
        service = self.services.get(service_name)

        if not service:
            return ServiceStatus(
                name=service_name,
                url="unknown",
                enabled=False,
                healthy=False,
                error="Service not found"
            )

        return ServiceStatus(
            name=service.name,
            url=service.url,
            enabled=service.enabled,
            healthy=service.healthy,
            latency_ms=service.latency_ms,
            error=service.error
        )

    def get_all_services(self) -> Dict[str, ServiceInfo]:
        """Retorna todos los servicios registrados"""
        return self.services

    def get_healthy_services(self) -> Dict[str, ServiceInfo]:
        """Retorna solo servicios saludables"""
        return {
            name: service
            for name, service in self.services.items()
            if service.healthy
        }

    async def stop_monitoring(self):
        """Detiene el monitoreo continuo"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
