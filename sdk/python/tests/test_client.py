"""Tests for the IdmClient using mocked HTTP (respx) and Redis (fakeredis)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from idm_sdk import IdmClient, IdmConfig, create_event

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config():
    return IdmConfig(
        core_url="http://idm-core:8888",
        api_key="test-secret-key",
        service_name="test-service",
        service_port=9000,
        redis_url="redis://localhost:6379",
    )


@pytest.fixture()
def mock_api():
    with respx.mock(base_url="http://idm-core:8888") as m:
        yield m


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


def test_config_from_env(monkeypatch):
    # IdmConfig usa env_prefix="VITAL_" (ver sdk/python/idm_sdk/config.py).
    # Todas las vars deben llevar ese prefix; los antiguos IDM_* del rebrand v0
    # ya no se reconocen sin alias explícito.
    monkeypatch.setenv("VITAL_CORE_URL", "http://core:1234")
    monkeypatch.setenv("VITAL_API_KEY", "env-key")
    monkeypatch.setenv("VITAL_SERVICE_NAME", "env-svc")
    monkeypatch.setenv("VITAL_SERVICE_PORT", "7777")
    monkeypatch.setenv("VITAL_REDIS_URL", "redis://r:6379/1")

    # _env_file=None desactiva la carga automática del .env del repo, que
    # contiene 52+ vars de operación y dispararía validation errors espurios.
    cfg = IdmConfig(_env_file=None)  # type: ignore[call-arg]
    assert cfg.core_url == "http://core:1234"
    assert cfg.api_key == "env-key"
    assert cfg.service_name == "env-svc"
    assert cfg.service_port == 7777
    assert cfg.redis_url == "redis://r:6379/1"


def test_config_defaults(config: IdmConfig):
    assert config.core_url == "http://idm-core:8888"
    assert config.service_name == "test-service"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check(config: IdmConfig, mock_api: respx.MockRouter):
    mock_api.get("/api/v1/health").mock(
        return_value=httpx.Response(200, json={"status": "ok", "timestamp": "2026-01-01T00:00:00Z"})
    )

    client = IdmClient(config)
    try:
        result = await client.health_check()
        assert result["status"] == "ok"
    finally:
        await client._http.aclose()


# ---------------------------------------------------------------------------
# Publish event
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_event(config: IdmConfig, mock_api: respx.MockRouter):
    route = mock_api.post("/api/v1/events").mock(
        return_value=httpx.Response(
            200,
            json={"event_id": "abc-123", "status": "created", "timestamp": "2026-01-01T00:00:00Z"},
        )
    )

    client = IdmClient(config)
    try:
        result = await client.publish_event(
            category="health",
            action="vitals.recorded",
            payload={"hr": 72},
            tags=["biometrics"],
        )
        assert result["status"] == "created"
        assert result["event_id"] == "abc-123"

        # Verify the request body matches EventCreate schema
        sent = json.loads(route.calls.last.request.content)
        assert sent["category"] == "health"
        assert sent["source"] == "test-service"
        assert sent["action"] == "vitals.recorded"
        assert sent["event_type"] == "sdk"
        assert sent["payload"] == {"hr": 72}
        assert sent["tags"] == ["biometrics"]
    finally:
        await client._http.aclose()


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_header(config: IdmConfig, mock_api: respx.MockRouter):
    mock_api.post("/api/v1/events").mock(
        return_value=httpx.Response(
            200,
            json={"event_id": "x", "status": "created", "timestamp": "t"},
        )
    )

    client = IdmClient(config)
    try:
        await client.publish_event("system", "test.action")
        req = mock_api.calls.last.request
        assert req.headers["X-API-Key"] == "test-secret-key"
    finally:
        await client._http.aclose()


@pytest.mark.asyncio
async def test_health_check_no_auth_header(config: IdmConfig, mock_api: respx.MockRouter):
    """Health endpoint is public -- but the client still sends the header
    (which idm-core simply ignores on the health router)."""
    mock_api.get("/api/v1/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )

    client = IdmClient(config)
    try:
        await client.health_check()
        req = mock_api.calls.last.request
        # The SDK always sends the key; idm-core ignores it on /health
        assert "X-API-Key" in req.headers
    finally:
        await client._http.aclose()


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register(config: IdmConfig, mock_api: respx.MockRouter):
    route = mock_api.post("/api/v1/events").mock(
        return_value=httpx.Response(
            200,
            json={"event_id": "reg-1", "status": "created", "timestamp": "t"},
        )
    )

    client = IdmClient(config)
    try:
        result = await client.register()
        assert result["status"] == "created"

        sent = json.loads(route.calls.last.request.content)
        assert sent["category"] == "system"
        assert sent["action"] == "service.registered"
        assert sent["source"] == "test-service"
        assert sent["payload"]["service_name"] == "test-service"
        assert sent["payload"]["service_port"] == 9000
    finally:
        await client._http.aclose()


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat(config: IdmConfig, mock_api: respx.MockRouter):
    route = mock_api.post("/api/v1/events").mock(
        return_value=httpx.Response(
            200,
            json={"event_id": "hb-1", "status": "created", "timestamp": "t"},
        )
    )

    client = IdmClient(config)
    try:
        result = await client.heartbeat()
        assert result["status"] == "created"

        sent = json.loads(route.calls.last.request.content)
        assert sent["category"] == "system"
        assert sent["action"] == "service.heartbeat"
        assert sent["source"] == "test-service"
    finally:
        await client._http.aclose()


# ---------------------------------------------------------------------------
# Connect / disconnect lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_disconnect(config: IdmConfig):
    with respx.mock(base_url="http://idm-core:8888", assert_all_called=False) as m:
        m.get("/api/v1/health").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        # heartbeat POST may or may not fire during the test
        m.post("/api/v1/events").mock(
            return_value=httpx.Response(
                200,
                json={"event_id": "x", "status": "created", "timestamp": "t"},
            )
        )

        client = IdmClient(config)
        await client.connect()

        # heartbeat task should be running
        assert client._heartbeat_task is not None
        assert not client._heartbeat_task.done()

        await client.disconnect()

        # heartbeat task should be cancelled
        assert client._heartbeat_task is None


@pytest.mark.asyncio
async def test_context_manager(config: IdmConfig):
    with respx.mock(base_url="http://idm-core:8888", assert_all_called=False) as m:
        m.get("/api/v1/health").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )
        m.post("/api/v1/events").mock(
            return_value=httpx.Response(
                200,
                json={"event_id": "x", "status": "created", "timestamp": "t"},
            )
        )

        async with IdmClient(config) as client:
            assert client._heartbeat_task is not None
            result = await client.health_check()
            assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# create_event helper
# ---------------------------------------------------------------------------


def test_create_event():
    ev = create_event(
        category="health",
        action="vitals.recorded",
        source="biohack-app",
        event_type="ingestion",
        payload={"hr": 72},
        metadata={"device": "apple_watch"},
        tags=["biometrics"],
        subcategory="vitals",
    )
    assert ev["category"] == "health"
    assert ev["subcategory"] == "vitals"
    assert ev["source"] == "biohack-app"
    assert ev["action"] == "vitals.recorded"
    assert ev["event_type"] == "ingestion"
    assert ev["payload"] == {"hr": 72}
    assert ev["metadata"] == {"device": "apple_watch"}
    assert ev["tags"] == ["biometrics"]


def test_create_event_defaults():
    ev = create_event(category="system", action="ping", source="sdk")
    assert ev["payload"] == {}
    assert ev["metadata"] == {}
    assert ev["tags"] == []
    assert ev["subcategory"] is None
    assert ev["event_type"] == "sdk"
