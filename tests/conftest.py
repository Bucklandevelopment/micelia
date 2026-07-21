"""
Shared fixtures for Micelia tests.
"""

import socket
import sys
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.health import ServiceStatus
from app.core.config import settings
from app.core.security import api_key_manager

# Make the in-tree Python SDK (`idm_sdk`) importable from the root test suite
# without requiring an editable install. The SDK lives in sdk/python/ and its
# own tests use that directory as their rootdir; root-level tests (e.g.
# test_idm_sdk.py) import it at runtime, so we add it to sys.path here.
_SDK_PYTHON = Path(__file__).resolve().parent.parent / "sdk" / "python"
if _SDK_PYTHON.is_dir() and str(_SDK_PYTHON) not in sys.path:
    sys.path.insert(0, str(_SDK_PYTHON))


# Generate a test API key that will be valid during tests
TEST_API_KEY = api_key_manager.generate_key(
    name="test",
    permissions={"all"},
    rate_limit=10000,
)


def _make_mock_service_status(**kwargs):
    """Create a ServiceStatus for health endpoint mocks."""
    defaults = dict(
        name="mock",
        url="http://mock:8080",
        enabled=True,
        healthy=True,
        latency_ms=1.0,
        error=None,
    )
    defaults.update(kwargs)
    return ServiceStatus(**defaults)


def _build_test_app() -> FastAPI:
    """Build a FastAPI app with mocked external dependencies for testing."""

    from app.api.v1 import ai, energy, events, frangels, gateway, health, system

    app = FastAPI()

    # Set up mocked state directly (no lifespan needed for tests)
    mock_service_registry = MagicMock()
    mock_service_registry.check_service = AsyncMock(
        return_value=_make_mock_service_status()
    )

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {}
    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_response)
    mock_http_client.post = AsyncMock(return_value=mock_response)

    app.state.http_client = mock_http_client
    app.state.service_registry = mock_service_registry
    app.state.event_bus = AsyncMock()
    app.state.event_store = None

    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(gateway.router, prefix="/api/v1", tags=["Gateway"])
    app.include_router(events.router, prefix="/api/v1", tags=["Events"])
    app.include_router(ai.router, prefix="/api/v1", tags=["AI"])
    app.include_router(energy.router, prefix="/api/v1", tags=["Energy"])
    app.include_router(system.router, prefix="/api/v1", tags=["System"])
    app.include_router(frangels.router, prefix="/api/v1", tags=["Frangels"])

    @app.get("/")
    async def root():
        return {"name": "Micelia", "version": "0.1.0", "status": "operational"}

    return app


@pytest.fixture(scope="session")
def test_app() -> FastAPI:
    return _build_test_app()


@pytest.fixture()
async def client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture()
def auth_headers() -> dict:
    """Headers with a valid API key for authenticated requests."""
    return {"X-API-Key": TEST_API_KEY}


# =============================================================================
# Hermeticidad de arranque del lifespan real (C85 → factorizada a conftest en C86)
# =============================================================================

# URLs de dominio que `discover_services` sondea al arrancar el lifespan real
# (`app.main:app`). Su default es `localhost:<puerto de dominio>` (config.py).
_PROBED_URL_ATTRS = (
    "health_service_url",
    "research_service_url",
    "education_service_url",
    "security_service_url",
    "imperio_lab_url",
)


def _closed_loopback_port() -> int:
    """Puerto de loopback garantizado CERRADO: lo bindea el SO y se suelta acto seguido."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def no_domain_probes(monkeypatch):
    """
    Hermeticidad para CUALQUIER test que arranque el lifespan REAL (`app.main:app`).

    Arrancar el lifespan dispara `discover_services`, que **sondea de verdad** los
    puertos de los dominios (localhost:8080/3690/5050/8000/8891). Sin fijar el entorno,
    el resultado depende de qué corra en la máquina del dev, no de lo que el test
    controla — la no-hermeticidad que C85 cazó en `test_main_boot_codex`. Esta fixture
    apunta TODOS los sondeos a un puerto de loopback cerrado → `connection_refused`
    determinista. Se conserva el sondeo REAL (no se mockea el cliente http): se fija el
    ENTORNO, no el comportamiento. Vive en conftest porque ya la comparten dos ficheros
    (boot smoke-test C85 + guard de registro C86).
    """
    closed = _closed_loopback_port()
    for attr in _PROBED_URL_ATTRS:
        monkeypatch.setattr(settings, attr, f"http://127.0.0.1:{closed}", raising=False)


@pytest.fixture()
def no_infra(monkeypatch, no_domain_probes):
    """
    Fuerza la condición "SIN infra" de forma determinista, para el test que asserta la
    degradación graciosa del gateway (event_store/user_store/prompt_store en None).

    Segundo eje de la no-hermeticidad de arranque (C86, corrige al addendum de C85, que
    solo barrió el eje de puertos-de-dominio): `..._without_infra` daba por hecho que
    PostgreSQL/Redis NO estaban — pero si el dev tiene postgres arriba (p.ej. tras
    `make docker-infra`), el lifespan inicializa el store real y el `assert ... is None`
    se pone ROJO, sin que nada esté mal. Lo destapó el propio guard de registro de C86 al
    correr la suite con postgres disponible.

    Además de los sondeos de dominio (via `no_domain_probes`), apunta `database_url` y
    `redis_url` a puertos de loopback cerrados → el store y el bus degradan por
    `connection_refused` determinista, hagan lo que hagan los contenedores de la máquina.
    """
    closed = _closed_loopback_port()
    monkeypatch.setattr(
        settings,
        "database_url",
        f"postgresql+asyncpg://idm:idm@127.0.0.1:{closed}/idm_core",
        raising=False,
    )
    monkeypatch.setattr(
        settings, "redis_url", f"redis://127.0.0.1:{closed}/0", raising=False
    )


@pytest.fixture()
async def require_postgres():
    """
    Skip-gate para los tests que exigen un Event Store real (PostgreSQL).

    Intenta inicializar un `EventStore` contra `settings.database_url` y hace `skip` si
    NO se puede (conexión rechazada, credenciales que no casan, DB ausente — todos
    significan "no hay store usable para esta config"). En local se satisface con el
    subconjunto de `make docker-infra` que levanta postgres; en su ausencia el test se
    salta en vez de fallar, igual que los guards cross-repo. Cede el store ya inicializado
    por si el test lo quiere consultar directamente, y lo cierra al terminar.
    """
    from app.events.store import EventStore

    store = EventStore()
    try:
        await store.initialize()
    except Exception as exc:  # noqa: BLE001 — cualquier fallo = sin postgres usable
        pytest.skip(f"PostgreSQL no disponible para {settings.database_url!r}: {exc}")
    try:
        yield store
    finally:
        await store.close()
