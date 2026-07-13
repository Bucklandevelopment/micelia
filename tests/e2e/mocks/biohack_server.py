"""
Mock server in-process para biohack-app, basado en respx.

Intercepta las requests HTTP que Micelia hace hacia ``settings.health_service_url``
y devuelve respuestas conformes al contrato definido en
``tests/e2e/mocks/contracts.py`` (T2.1).

Uso:
    @pytest.mark.asyncio
    async def test_something(biohack_mock):
        biohack_mock.set_mode("healthy")
        ...

Modos soportados:
    ``"healthy"``  → todos los endpoints responden 200 con datos válidos.
    ``"degraded"`` → /health responde "degraded", subset de servicios unhealthy.
    ``"down"``     → todos los endpoints responden 503.
    ``"slow"``     → respuestas tardan ``slow_delay_seconds`` (default 2s) y
                     luego responden como en healthy. Útil para tests de timeout.

Limitaciones conocidas
======================
- ``respx.MockRouter`` no aplica el ``base_url`` que se le pase como kwarg al
  registrar rutas relativas en todas las versiones; aquí componemos URLs
  absolutas explícitas (``f"{base_url}{path}"``) para que los matchers sean
  estables.
- Para el modo ``"slow"`` usamos un ``side_effect`` síncrono que duerme con
  ``time.sleep``. Respx invoca el side_effect dentro del loop de evento; un
  ``asyncio.sleep`` requeriría un side_effect async (no soportado en todas
  las versiones), así que aceptamos el bloqueo del thread por simplicidad.
- ``BiohackMock`` NO valida estrictamente el body de los POST: se intenta
  parsear el JSON; si falla devuelve 422. Esto sigue la regla del brief:
  "acepta cualquier body válido pero devuelve 422 si el JSON es malformado".

Reglas de implementación
========================
- Las respuestas se construyen instanciando los modelos Pydantic de
  ``contracts.py`` (que tienen ``extra="forbid"``) y serializándolas con
  ``model.model_dump(mode="json")``. Esto garantiza conformidad estricta:
  si en el futuro el contrato cambia, el mock falla en construcción y no
  emite un payload silenciosamente roto.
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from httpx import Request, Response

from .contracts import (
    BiomarkerPoint,
    BiomarkerSeries,
    BioSavantChatRequest,
    BioSavantChatResponse,
    BioSavantSource,
    HealthDetailed,
    HealthReady,
    HealthResources,
    HealthServicesResponse,
    HealthStatus,
    MLPredictionRequest,
    MLPredictionResponse,
    ServiceStatusEntry,
)

MockMode = Literal["healthy", "degraded", "down", "slow"]

_VALID_MODES: tuple[MockMode, ...] = ("healthy", "degraded", "down", "slow")

#: Paths bajo el contrato. Se mantienen agrupados para facilitar el barrido en
#: ``_setup_routes`` (cada modo cubre TODOS los paths).
_PATH_HEALTH = "/api/v1/health"
_PATH_HEALTH_LIVE = "/api/v1/health/live"
_PATH_HEALTH_READY = "/api/v1/health/ready"
_PATH_HEALTH_DETAILED = "/api/v1/health/detailed"
_PATH_HEALTH_SERVICES = "/api/v1/health/services"
_PATH_BIOSAVANT_CHAT = "/api/v1/bio-savant/chat"
_PATH_ML_PREDICT = "/api/v1/ml-production/predict"
_PATH_BIOMARKERS_SERIES = "/api/v1/biomarkers/series"


def _now() -> datetime:
    """Timestamp determinista-friendly: ``datetime.now(tz=UTC)`` truncado a μs."""
    return datetime.now(tz=timezone.utc)


def _seed_for(user_id: str, metric: str) -> int:
    """Seed determinista para series de biomarkers."""
    return hash(f"{user_id}|{metric}") & 0xFFFFFFFF


def _parse_query(request: Request) -> dict[str, str]:
    """Extrae query params planos (último valor gana)."""
    parsed = urlparse(str(request.url))
    raw = parse_qs(parsed.query, keep_blank_values=True)
    return {k: v[-1] for k, v in raw.items() if v}


class BiohackMock:
    """Controlador del mock biohack-app.

    Encapsula un ``respx.MockRouter`` y reconfigura sus rutas cada vez que
    cambia ``mode``. La fixture ``biohack_mock`` lo instancia y delega aquí
    toda la lógica de fixture/teardown.
    """

    def __init__(
        self,
        mock: respx.MockRouter,
        base_url: str,
        slow_delay_seconds: float = 2.0,
    ) -> None:
        self._mock = mock
        self._base_url = base_url.rstrip("/")
        self._mode: MockMode = "healthy"
        self.slow_delay_seconds = slow_delay_seconds
        # Routes registrados en respx; se limpian en cada ``set_mode``.
        self._routes: list[respx.Route] = []

    # ------------------------------------------------------------------ API

    @property
    def mode(self) -> MockMode:
        return self._mode

    @mode.setter
    def mode(self, value: MockMode) -> None:
        self.set_mode(value)

    @property
    def base_url(self) -> str:
        return self._base_url

    def set_mode(self, mode: MockMode) -> None:
        """Cambia el modo y reconfigura todas las rutas en respx."""
        if mode not in _VALID_MODES:
            raise ValueError(
                f"BiohackMock.set_mode: modo {mode!r} desconocido; "
                f"válidos: {_VALID_MODES}"
            )
        self._mode = mode
        self._mock.reset()
        self._routes.clear()
        self._setup_routes()

    def reset(self) -> None:
        """Limpia rutas sin tocar el modo (útil entre asserts)."""
        self._mock.reset()
        self._routes.clear()
        self._setup_routes()

    # ----------------------------------------------------------- internals

    def _url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def _setup_routes(self) -> None:
        """Registra todas las rutas en respx según ``self._mode``.

        Para ``"down"`` todas las rutas devuelven 503; para los otros modos,
        cada handler decide su payload y status según el modo.
        """
        # GETs: respuesta estática (con/sin slow delay).
        self._routes.append(
            self._mock.get(self._url(_PATH_HEALTH)).mock(
                side_effect=self._wrap(self._health_response)
            )
        )
        self._routes.append(
            self._mock.get(self._url(_PATH_HEALTH_LIVE)).mock(
                side_effect=self._wrap(self._health_live_response)
            )
        )
        self._routes.append(
            self._mock.get(self._url(_PATH_HEALTH_READY)).mock(
                side_effect=self._wrap(self._health_ready_response)
            )
        )
        self._routes.append(
            self._mock.get(self._url(_PATH_HEALTH_DETAILED)).mock(
                side_effect=self._wrap(self._health_detailed_response)
            )
        )
        self._routes.append(
            self._mock.get(self._url(_PATH_HEALTH_SERVICES)).mock(
                side_effect=self._wrap(self._health_services_response)
            )
        )
        # GET biomarkers: lee query params, puede devolver 400 si faltan.
        self._routes.append(
            self._mock.get(self._url(_PATH_BIOMARKERS_SERIES)).mock(
                side_effect=self._wrap(self._biomarkers_series_response)
            )
        )
        # POSTs.
        self._routes.append(
            self._mock.post(self._url(_PATH_BIOSAVANT_CHAT)).mock(
                side_effect=self._wrap(self._biosavant_chat_response)
            )
        )
        self._routes.append(
            self._mock.post(self._url(_PATH_ML_PREDICT)).mock(
                side_effect=self._wrap(self._ml_predict_response)
            )
        )

    def _wrap(self, handler):
        """Envuelve un handler aplicando políticas globales (down, slow).

        - En modo ``"down"`` devolvemos 503 sin invocar el handler.
        - En modo ``"slow"`` insertamos un ``time.sleep`` antes de delegar al
          handler (que se comporta como en ``"healthy"``).
        """

        def _route(request: Request) -> Response:
            if self._mode == "down":
                return Response(
                    503,
                    json={"detail": "biohack-app unavailable"},
                )
            if self._mode == "slow":
                time.sleep(self.slow_delay_seconds)
            return handler(request)

        return _route

    # --------------------------------------------------------- GET handlers

    def _health_response(self, request: Request) -> Response:
        status_value: Literal["ok", "degraded"] = (
            "degraded" if self._mode == "degraded" else "ok"
        )
        payload = HealthStatus(
            status=status_value,
            timestamp=_now(),
            service="biohack-app",
            version="0.1.0",
        )
        return Response(200, json=payload.model_dump(mode="json"))

    def _health_live_response(self, request: Request) -> Response:
        payload = HealthStatus(
            status="alive",
            timestamp=_now(),
            service="biohack-app",
            version="0.1.0",
        )
        return Response(200, json=payload.model_dump(mode="json"))

    def _health_ready_response(self, request: Request) -> Response:
        if self._mode == "degraded":
            payload = HealthReady(
                status="not_ready",
                timestamp=_now(),
                reason="ml-models loading",
            )
        else:
            payload = HealthReady(status="ready", timestamp=_now())
        return Response(200, json=payload.model_dump(mode="json"))

    def _health_detailed_response(self, request: Request) -> Response:
        # Compone el dict de servicios; en modo degraded, "database" sale roto.
        database_healthy = self._mode != "degraded"
        services: dict[str, ServiceStatusEntry] = {
            "database": ServiceStatusEntry(
                name="postgres",
                url="postgres://biohack-db:5432/biohack",
                enabled=True,
                healthy=database_healthy,
                latency_ms=1.2 if database_healthy else None,
                error=None if database_healthy else "connection refused",
            ),
            "ml_models": ServiceStatusEntry(
                name="onnx",
                url="local://models",
                enabled=True,
                healthy=True,
                latency_ms=None,
                error=None,
            ),
        }
        overall = "degraded" if self._mode == "degraded" else "healthy"
        payload = HealthDetailed(
            status=overall,
            timestamp=_now(),
            uptime_seconds=1234.5,
            services=services,
            resources=HealthResources(
                cpu_percent=12.3,
                memory={"total_gb": 16.0, "available_gb": 9.4, "percent": 41.0},
                disk={"total_gb": 500.0, "free_gb": 200.5, "percent": 60.0},
            ),
        )
        return Response(200, json=payload.model_dump(mode="json"))

    def _health_services_response(self, request: Request) -> Response:
        canela_healthy = self._mode != "degraded"
        # URLs = defaults reales de `app/core/config.py` (topología local-first).
        # En docker-compose son los hostnames de contenedor equivalentes
        # (biohack-app:8080, canela-molida:3690, ideacursi-backend:5050,
        # cybertools:8000). NO usar puertos inventados: el registry real
        # (`app/services/service_registry.py`) refleja `settings.*_service_url`.
        services: dict[str, ServiceStatusEntry] = {
            "health": ServiceStatusEntry(
                name="biohack-app",
                url="http://localhost:8080",
                enabled=True,
                healthy=True,
                latency_ms=1.4,
                error=None,
            ),
            "research": ServiceStatusEntry(
                name="canela-molida",
                url="http://localhost:3690",
                enabled=True,
                healthy=canela_healthy,
                latency_ms=2.1 if canela_healthy else None,
                error=None if canela_healthy else "timeout",
            ),
            "education": ServiceStatusEntry(
                name="ideacursi-tool",
                url="http://localhost:5050",
                enabled=True,
                healthy=True,
                latency_ms=2.1,
                error=None,
            ),
            "security": ServiceStatusEntry(
                name="cybertools",
                url="http://localhost:8000",
                enabled=True,
                healthy=True,
                latency_ms=1.8,
                error=None,
            ),
        }
        payload = HealthServicesResponse(services=services)
        return Response(200, json=payload.model_dump(mode="json"))

    def _biomarkers_series_response(self, request: Request) -> Response:
        params = _parse_query(request)
        user_id = params.get("user_id")
        metric = params.get("metric")
        if not user_id or not metric:
            return Response(
                400,
                json={
                    "detail": (
                        "Missing required query params: user_id and metric"
                    )
                },
            )

        rng = random.Random(_seed_for(user_id, metric))
        unit = {"hrv": "ms", "vo2max": "ml/kg/min", "weight": "kg"}.get(
            metric, "unit"
        )
        # 30 puntos diarios, ancla en hoy a 08:00 UTC, retrocediendo.
        anchor = _now().replace(hour=8, minute=0, second=0, microsecond=0)
        baseline = {"hrv": 75.0, "vo2max": 48.0, "weight": 72.0}.get(
            metric, 50.0
        )
        points: list[BiomarkerPoint] = []
        for day in range(29, -1, -1):
            ts = anchor - timedelta(days=day)
            jitter = rng.uniform(-3.0, 3.0)
            value = round(baseline + jitter, 2)
            points.append(BiomarkerPoint(timestamp=ts, value=value))

        payload = BiomarkerSeries(
            user_id=user_id, metric=metric, unit=unit, points=points
        )
        return Response(200, json=payload.model_dump(mode="json"))

    # -------------------------------------------------------- POST handlers

    def _biosavant_chat_response(self, request: Request) -> Response:
        try:
            body = json.loads(request.content or b"{}")
        except json.JSONDecodeError:
            return Response(
                422, json={"detail": "Invalid JSON in request body"}
            )
        # Validación laxa: el modelo permite extra="forbid" así que validar
        # estrictamente rompería clientes futuros que añadan campos. Sólo
        # comprobamos que `message` esté presente (única validación que el
        # endpoint real haría como sanity check).
        if not isinstance(body, dict) or "message" not in body:
            return Response(
                422, json={"detail": "Missing required field: message"}
            )
        # Best-effort: si el cliente envía un body 100 % conforme, validamos.
        try:
            BioSavantChatRequest(**body)
        except Exception:
            # Aceptamos clientes con campos extra; sólo registramos vía contrato
            # cuando coincide. No bloqueamos.
            pass

        payload = BioSavantChatResponse(
            answer=(
                "Tu VO2max ha caído 3.1 puntos en 14 días; revisa carga "
                "aeróbica y descanso."
            ),
            sources=[
                BioSavantSource(
                    title="Heart Rate Variability and Recovery",
                    url="https://pubmed.ncbi.nlm.nih.gov/example/1",
                    confidence=0.87,
                ),
                BioSavantSource(
                    title="VO2max Trends in Endurance Athletes",
                    url="https://pubmed.ncbi.nlm.nih.gov/example/2",
                    confidence=0.74,
                ),
            ],
            reasoning_trace=[
                "Filtered to last 30 days",
                "Compared 7d vs 30d rolling mean",
                "Selected top 2 citations by confidence",
            ],
        )
        return Response(200, json=payload.model_dump(mode="json"))

    def _ml_predict_response(self, request: Request) -> Response:
        try:
            body = json.loads(request.content or b"{}")
        except json.JSONDecodeError:
            return Response(
                422, json={"detail": "Invalid JSON in request body"}
            )
        if not isinstance(body, dict):
            return Response(
                422, json={"detail": "Request body must be a JSON object"}
            )
        # Sanity check: al menos uno de los tres sub-grupos del contrato.
        if not any(k in body for k in ("metrics", "features", "model_name")):
            return Response(
                422,
                json={
                    "detail": (
                        "Must provide at least one of: metrics, features, "
                        "model_name"
                    )
                },
            )
        try:
            MLPredictionRequest(**body)
        except Exception:
            pass

        payload = MLPredictionResponse(
            prediction=0.71,
            confidence=0.84,
            model_version="energy@1.2.0",
        )
        return Response(200, json=payload.model_dump(mode="json"))


# =============================================================================
# pytest fixtures
# =============================================================================


@pytest.fixture
def biohack_mock():
    """Fixture function-scoped que monta el mock biohack-app.

    Lee ``settings.health_service_url`` para componer el ``base_url`` que
    respx interceptará. Cualquier llamada de Micelia que escape al mock
    (paths no declarados) levantará ``respx.MockResponseNotFoundError`` con
    ``assert_all_called=False`` la fixture no obliga a usar todas las rutas.
    """
    from app.core.config import settings

    base_url = settings.health_service_url.rstrip("/")
    with respx.mock(base_url=base_url, assert_all_called=False) as mock:
        biohack = BiohackMock(mock=mock, base_url=base_url)
        biohack.set_mode("healthy")  # default
        yield biohack


@pytest.fixture(scope="module")
def biohack_mock_module():
    """Variante module-scoped para suites que comparten el mismo modo.

    Uso cuando varios tests del mismo módulo asumen ``healthy`` y montar/
    desmontar respx por test añade overhead innecesario.
    """
    from app.core.config import settings

    base_url = settings.health_service_url.rstrip("/")
    with respx.mock(base_url=base_url, assert_all_called=False) as mock:
        biohack = BiohackMock(mock=mock, base_url=base_url)
        biohack.set_mode("healthy")
        yield biohack


__all__ = (
    "BiohackMock",
    "MockMode",
    "biohack_mock",
    "biohack_mock_module",
)
