"""
Tests for Micelia SDK (app.sdk).

Mocks the Micelia REST API to validate SDK behavior
without requiring a running Micelia instance.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.sdk import HealthResponse, IdmEvent, IdmServiceClient, MiceliaServiceClient
from app.sdk.models import EVENT_CHANNELS

# =============================================================================
# Model tests
# =============================================================================


class TestHealthResponse:
    def test_to_dict(self):
        hr = HealthResponse(
            status="healthy",
            version="1.0.0",
            service="test-svc",
            category="health",
            port=8080,
            capabilities=["ml", "rag"],
            uptime_seconds=120.5,
            dependencies={"postgresql": "healthy"},
        )
        d = hr.to_dict()
        assert d["status"] == "healthy"
        assert d["service"] == "test-svc"
        assert d["port"] == 8080
        assert d["capabilities"] == ["ml", "rag"]
        assert d["dependencies"]["postgresql"] == "healthy"

    def test_defaults(self):
        hr = HealthResponse(
            status="healthy",
            version="0.1.0",
            service="x",
            category="system",
            port=9999,
            capabilities=[],
            uptime_seconds=0,
        )
        assert hr.dependencies == {}


class TestIdmEvent:
    def test_to_dict_minimal(self):
        ev = IdmEvent(
            category="health",
            source="biohack",
            action="create",
            event_type="biomarker.recorded",
        )
        d = ev.to_dict()
        assert d["category"] == "health"
        assert d["source"] == "biohack"
        assert d["action"] == "create"
        assert d["event_type"] == "biomarker.recorded"
        # None values should be excluded
        assert "subcategory" not in d
        assert "correlation_id" not in d

    def test_to_dict_full(self):
        ev = IdmEvent(
            category="education",
            source="ideacursi",
            action="update",
            event_type="lesson.completed",
            payload={"lesson_id": "abc"},
            subcategory="learning",
            metadata={"sdk_version": "1.0.0"},
            tags=["quiz"],
            correlation_id="corr-123",
        )
        d = ev.to_dict()
        assert d["subcategory"] == "learning"
        assert d["correlation_id"] == "corr-123"
        assert d["tags"] == ["quiz"]


class TestConstants:
    def test_event_channels_aligned(self):
        """Channels must match EventBus.CHANNELS in event_bus.py."""
        assert EVENT_CHANNELS["health"] == "idm.health"
        assert EVENT_CHANNELS["education"] == "idm.education"
        assert EVENT_CHANNELS["security"] == "idm.security"
        assert EVENT_CHANNELS["system"] == "idm.system"

    def test_eventbus_channels_derive_from_sdk(self):
        """Invariante anti-drift: EventBus.CHANNELS es superset del contrato
        público del SDK (EVENT_CHANNELS) y todo canal compartido tiene un valor
        IDÉNTICO. Caza que runtime y contrato deriven (ej. renombrar el prefijo
        en un solo sitio). "prompts" es interno del orquestador → solo en
        EventBus.CHANNELS, no en el mapa público."""
        from app.services.event_bus import EventBus

        for category, channel in EVENT_CHANNELS.items():
            assert EventBus.CHANNELS.get(category) == channel, (
                f"drift en canal '{category}': SDK={channel} "
                f"vs EventBus={EventBus.CHANNELS.get(category)}"
            )
        # El único canal que EventBus añade sobre el contrato público es el
        # interno "prompts".
        extra = set(EventBus.CHANNELS) - set(EVENT_CHANNELS)
        assert extra == {"prompts"}, f"canales extra inesperados: {extra}"


# =============================================================================
# Client tests
# =============================================================================


def _make_client(**kwargs) -> MiceliaServiceClient:
    defaults = dict(
        service_name="test-service",
        port=9999,
        category="health",
        micelia_url="http://localhost:8888",
        api_key="test-key-123",
        version="0.5.0",
        capabilities=["test"],
        heartbeat_interval=0,  # disable heartbeat for unit tests
    )
    defaults.update(kwargs)
    return MiceliaServiceClient(**defaults)


def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = ""
    resp.json.return_value = json_data or {}
    return resp


class TestClientInit:
    def test_defaults(self):
        c = _make_client()
        assert c.service_name == "test-service"
        assert c.port == 9999
        assert c.category == "health"
        assert c.api_key == "test-key-123"
        assert c.version == "0.5.0"
        assert c.capabilities == ["test"]

    def test_url_trailing_slash_stripped(self):
        c = _make_client(micelia_url="http://example.com/")
        assert c.micelia_url == "http://example.com"


class TestHealthResponseGeneration:
    def test_healthy_by_default(self):
        c = _make_client()
        c._started_at = None  # not started yet
        hr = c.health_response()
        assert hr.status == "healthy"
        assert hr.service == "test-service"
        assert hr.version == "0.5.0"
        assert hr.category == "health"
        assert hr.port == 9999
        assert hr.uptime_seconds == 0.0

    def test_degraded_when_dependency_unhealthy(self):
        c = _make_client()
        hr = c.health_response(dependencies={"db": "healthy", "redis": "unhealthy"})
        assert hr.status == "degraded"

    def test_unhealthy_when_set(self):
        c = _make_client()
        c.set_healthy(False, error="DB connection lost")
        hr = c.health_response()
        assert hr.status == "unhealthy"

    def test_status_override(self):
        c = _make_client()
        c.set_healthy(False)
        hr = c.health_response(status_override="healthy")
        assert hr.status == "healthy"


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(
            return_value=_mock_response(200, {"event_id": "abc-123"})
        )

        result = await c.register()
        assert result is True

        # Verify the POST was made to the events endpoint
        call_args = c._http_client.post.call_args
        assert "/api/v1/events" in call_args.args[0]
        body = call_args.kwargs["json"]
        assert body["category"] == "system"
        assert body["source"] == "test-service"
        assert body["event_type"] == "service.registered"
        assert body["payload"]["port"] == 9999

    @pytest.mark.asyncio
    async def test_register_failure(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(return_value=_mock_response(500))

        result = await c.register()
        assert result is False

    @pytest.mark.asyncio
    async def test_register_connection_error(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        result = await c.register()
        assert result is False


class TestHeartbeat:
    @pytest.mark.asyncio
    async def test_heartbeat_success(self):
        c = _make_client()
        c._started_at = None
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(
            return_value=_mock_response(200, {"event_id": "hb-1"})
        )

        result = await c.heartbeat()
        assert result is True

        body = c._http_client.post.call_args.kwargs["json"]
        assert body["event_type"] == "service.heartbeat"
        assert body["payload"]["status"] == "healthy"
        assert body["payload"]["service"] == "test-service"

    @pytest.mark.asyncio
    async def test_heartbeat_failure(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(side_effect=Exception("timeout"))

        result = await c.heartbeat()
        assert result is False


class TestPublishEvent:
    @pytest.mark.asyncio
    async def test_publish_event_success(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(
            return_value=_mock_response(200, {"event_id": "ev-42"})
        )

        event_id = await c.publish_event(
            category="health",
            action="create",
            event_type="biomarker.recorded",
            payload={"heart_rate": 72},
            tags=["vitals"],
        )
        assert event_id == "ev-42"

        body = c._http_client.post.call_args.kwargs["json"]
        assert body["category"] == "health"
        assert body["source"] == "test-service"
        assert body["action"] == "create"
        assert body["event_type"] == "biomarker.recorded"
        assert body["payload"]["heart_rate"] == 72
        assert body["tags"] == ["vitals"]

    @pytest.mark.asyncio
    async def test_publish_event_with_correlation(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(
            return_value=_mock_response(200, {"event_id": "ev-99"})
        )

        event_id = await c.publish_event(
            category="education",
            action="update",
            event_type="lesson.completed",
            correlation_id="workflow-abc",
        )
        assert event_id == "ev-99"

        body = c._http_client.post.call_args.kwargs["json"]
        assert body["correlation_id"] == "workflow-abc"

    @pytest.mark.asyncio
    async def test_publish_event_failure(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(return_value=_mock_response(503))

        event_id = await c.publish_event(
            category="system",
            action="create",
            event_type="test.event",
        )
        assert event_id is None


class TestPublishEventBus:
    @pytest.mark.asyncio
    async def test_fallback_to_rest_when_no_redis(self):
        """When Redis is not connected, publish_event_bus falls back to REST."""
        c = _make_client()
        c._redis = None
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(
            return_value=_mock_response(200, {"event_id": "fb-1"})
        )

        result = await c.publish_event_bus(
            category="health",
            event_type="vitals.updated",
            data={"bpm": 65},
        )
        assert result is True
        # Should have called the REST endpoint
        c._http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_via_redis(self):
        """When Redis is connected, publish directly to pub/sub."""
        c = _make_client()
        c._redis = AsyncMock()
        c._redis.publish = AsyncMock()

        result = await c.publish_event_bus(
            category="health",
            event_type="vitals.updated",
            data={"bpm": 65},
        )
        assert result is True

        # Verify Redis publish was called with correct channel
        call_args = c._redis.publish.call_args
        assert call_args.args[0] == "idm.health"


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_creates_http_client_and_registers(self):
        c = _make_client()

        with patch.object(c, "register", new_callable=AsyncMock) as mock_register:
            mock_register.return_value = True
            await c.start()

            assert c._http_client is not None
            assert c._started_at is not None
            mock_register.assert_called_once()

            await c.stop()
            # After stop, http client should be closed
            assert c._http_client.is_closed

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        """Calling stop on a non-started client should not raise."""
        c = _make_client()
        await c.stop()  # Should not raise


class TestAuthHeaders:
    def test_headers_include_api_key(self):
        c = _make_client(api_key="my-secret-key")
        headers = c._auth_headers()
        assert headers["X-API-Key"] == "my-secret-key"

    def test_headers_without_api_key(self):
        c = _make_client(api_key="")
        headers = c._auth_headers()
        assert "X-API-Key" not in headers


import httpx  # noqa: E402 - imported here for ConnectError in test

# =============================================================================
# Deprecation alias tests
# =============================================================================


def test_idm_client_alias_deprecation():
    """The legacy `IdmClient` alias on `idm_sdk` must still work but emit a
    DeprecationWarning at INSTANTIATION (changed in T5.4: alias is now a
    subclass that warns in __init__, not a module-level identity alias).

    Mirrors the same alias contract in `app.sdk` where `IdmServiceClient`
    continues to work as a deprecated alias of `MiceliaServiceClient`.
    """
    import warnings

    # idm_sdk package: IdmClient is a subclass of MiceliaClient (post-T5.4)
    from idm_sdk import IdmClient, IdmConfig, MiceliaClient

    assert issubclass(IdmClient, MiceliaClient)
    # IdmClient is no longer the exact same object (it's a deprecated subclass)
    assert IdmClient is not MiceliaClient

    # Instantiation emits DeprecationWarning
    cfg = IdmConfig(
        core_url="http://test:8888",
        api_key="k",
        service_name="alias-test",
        service_port=1234,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = IdmClient(cfg)
        assert any(
            issubclass(w.category, DeprecationWarning) for w in caught
        ), "Expected DeprecationWarning when instantiating IdmClient"
    assert isinstance(client, MiceliaClient)

    # app.sdk: IdmServiceClient must alias MiceliaServiceClient; instantiating
    # via the deprecated `idm_core_url` kwarg must emit a DeprecationWarning.
    assert IdmServiceClient is MiceliaServiceClient

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        client = IdmServiceClient(
            service_name="alias-test",
            port=1234,
            category="system",
            idm_core_url="http://legacy:8888",
            heartbeat_interval=0,
        )
        assert any(
            issubclass(w.category, DeprecationWarning) for w in caught
        ), "Expected DeprecationWarning when using `idm_core_url` kwarg"

    assert client.micelia_url == "http://legacy:8888"
