"""
Shared fixtures for Micelia tests.
"""

import sys
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.health import ServiceStatus
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
