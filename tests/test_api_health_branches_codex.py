"""
Branch coverage for app/api/v1/health.py that the endpoint-level tests in
tests/test_health.py don't reach: the readiness "not_ready" path and the three
overall-status branches of /health/detailed (healthy / degraded / unhealthy).

The handlers only touch ``request.app.state.service_registry.check_service``, so
we call them directly with a fake Request whose registry is an AsyncMock — no
ASGI, no infra. ``check_service`` is awaited once per service; we drive its
outcomes with ``side_effect``/``return_value`` of ServiceStatus objects.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api.v1.health import (
    ServiceStatus,
    detailed_health,
    readiness_check,
)


def _status(healthy: bool) -> ServiceStatus:
    return ServiceStatus(
        name="svc",
        url="http://svc:8080",
        enabled=True,
        healthy=healthy,
        latency_ms=1.0,
        error=None if healthy else "down",
    )


def _request(registry) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        service_registry=registry
    )))


def _registry(*, side_effect=None, healthy=True) -> AsyncMock:
    registry = AsyncMock()
    if side_effect is not None:
        registry.check_service = AsyncMock(side_effect=side_effect)
    else:
        registry.check_service = AsyncMock(return_value=_status(healthy))
    return registry


# ==================== readiness ====================


async def test_readiness_ready_when_any_critical_up():
    # health up, research down -> ready (OR branch already true on first)
    reg = _registry(side_effect=[_status(True), _status(False)])
    result = await readiness_check(_request(reg))
    assert result["status"] == "ready"
    assert "timestamp" in result


async def test_readiness_not_ready_when_all_critical_down():
    reg = _registry(side_effect=[_status(False), _status(False)])
    result = await readiness_check(_request(reg))
    assert result == {
        "status": "not_ready",
        "reason": "No critical services available",
    }


# ==================== detailed: overall_status branches ====================


async def test_detailed_all_healthy():
    reg = _registry(healthy=True)
    health = await detailed_health(_request(reg))
    assert health.status == "healthy"
    assert set(health.services) == {"health", "research", "education", "security"}


async def test_detailed_degraded_when_mixed():
    # first service healthy, rest down -> any_healthy True, all_healthy False
    reg = _registry(side_effect=[
        _status(True), _status(False), _status(False), _status(False),
    ])
    health = await detailed_health(_request(reg))
    assert health.status == "degraded"


async def test_detailed_unhealthy_when_all_down():
    reg = _registry(healthy=False)
    health = await detailed_health(_request(reg))
    assert health.status == "unhealthy"
    assert all(not s.healthy for s in health.services.values())
