"""
Service Registry: Descubrimiento y monitoreo de microservicios.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

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

    # Fuente ÚNICA de verdad del endpoint de health por dominio. Se consume tanto
    # en el chequeo inicial (`discover_services`) como en el monitoreo continuo
    # (`_continuous_monitoring`); antes estaba duplicado en ambos y podía derivar
    # (un dominio cambia su ruta y solo se actualiza una copia → discovery y
    # monitoring sondeando URLs distintas). Cada ruta está anclada al handler REAL
    # que sirve el dominio hermano (verificado por lectura de su código):
    #   - health   (biohack-app):   /api/v1/service-health  (backend/main.py:209,
    #                                @app.get("/api/v1/service-health"))
    #   - research (canela-molida):  /health                (app/main.py:505)
    #   - education (ideacursi-tool): /api/health            (setGlobalPrefix('api')
    #                                + @Controller('health') + @Get())
    #   - security (cybertools):     /health                (src/scanet/api.py:127)
    #   - testlab  (imperio-lab):    /health
    # (el slot `devtools`/ollama-code se ELIMINÓ en C118 — C84-minor, decisión de Jessicache:
    #  ollama-code no es un proyecto planificado.)
    HEALTH_ENDPOINTS: Dict[str, str] = {
        "health": "/api/v1/service-health",
        "research": "/health",
        "education": "/api/health",
        "security": "/health",
        "testlab": "/health",
    }

    def __init__(self, http_client: httpx.AsyncClient):
        self.client = http_client
        self.services: Dict[str, ServiceInfo] = {}
        self._check_interval = settings.health_check_interval
        self._monitoring_task: Optional[asyncio.Task] = None

    async def discover_services(self):
        """Descubre y registra todos los servicios configurados"""

        # El endpoint de health sale de HEALTH_ENDPOINTS (fuente única); aquí solo
        # se definen url + enabled por dominio.
        service_configs: Dict[str, Dict[str, Any]] = {
            "health": {
                "url": settings.health_service_url,
                "enabled": settings.health_service_enabled,
                "health_endpoint": self.HEALTH_ENDPOINTS["health"],
            },
            "research": {
                "url": settings.research_service_url,
                "enabled": settings.research_service_enabled,
                "health_endpoint": self.HEALTH_ENDPOINTS["research"],
            },
            "education": {
                "url": settings.education_service_url,
                "enabled": settings.education_service_enabled,
                "health_endpoint": self.HEALTH_ENDPOINTS["education"],
            },
            "security": {
                "url": settings.security_service_url,
                "enabled": settings.security_service_enabled,
                "health_endpoint": self.HEALTH_ENDPOINTS["security"],
            },
            "testlab": {
                "url": settings.imperio_lab_url,
                "enabled": settings.imperio_lab_enabled,
                "health_endpoint": self.HEALTH_ENDPOINTS["testlab"],
            },
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
            # El comando que de verdad los levanta depende de la TOPOLOGÍA en la que
            # corre ESTE gateway, y esa se deduce de las URLs que sondea (DP-15, C85):
            #
            #  * localhost/127.0.0.1 → gateway NATIVO (run-local.sh), que es el caso
            #    por defecto (los defaults de config.py son localhost:*). Aquí el
            #    comando correcto es el launcher local-first: bindea EXACTAMENTE los
            #    puertos que sondeamos (health :8080, research :3690, education :5050,
            #    security :8000, testlab :8891).
            #    `make docker-full` NO sirve a un gateway nativo: el compose PUBLICA
            #    health en :8081 y testlab (auto-mat-ion) en :3100 → 2 de 5 seguirían
            #    unhealthy después de levantar 9 contenedores. Recomendarlo era una
            #    promesa que el comando no puede cumplir.
            #  * hostnames de contenedor (biohack-app, canela-molida, …) → gateway EN
            #    COMPOSE: ahí los puertos son internos y sí manda el compose.
            #
            # Pineado en tests/test_registry_hint_topology_codex.py.
            unhealthy_names = {s.name for s in unhealthy}
            gateway_is_native = all(
                (urlparse(s.url).hostname or "") in ("localhost", "127.0.0.1")
                for s in unhealthy
            )
            if gateway_is_native:
                hint = "scripts/run-ecosystem.sh start"
            elif unhealthy_names == {"health"}:
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
                        # Endpoint desde HEALTH_ENDPOINTS (misma fuente que el
                        # chequeo inicial); .get() evita KeyError si algún
                        # servicio del registry no lo declara.
                        endpoint = self.HEALTH_ENDPOINTS.get(name, "/health")
                        await self._check_health(name, endpoint)

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
            error=service.error,
            # `version` la captura `_check_health` desde el body del health-check
            # del dominio; antes se quedaba en ServiceInfo sin llegar a ningún
            # endpoint. Se propaga para que /api/v1/health/{services,detailed} la
            # expongan (contrato auditado en Ciclo 42).
            version=service.version
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
