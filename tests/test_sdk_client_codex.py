"""
Cobertura complementaria de ``app/sdk/client.py`` (IdmServiceClient) — Ciclo 31.

El test existente ``test_idm_sdk.py`` cubre el happy path de register/heartbeat/
publish_event y el pub/sub básico. Aquí se cierran los huecos restantes
(59%→~100%): lifecycle (``start``/``stop`` con recursos vivos), ``_heartbeat_loop``,
ramas de error de eventos, ``subscribe``/``_listen_loop`` de Redis pub/sub, la
propiedad deprecada ``idm_core_url`` y ``_connect_redis``.

Todo se mockea in-process (``AsyncMock`` para http/redis, igual que el test
existente). No toca red, infra, ``.env`` ni subprocess.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.sdk import IdmServiceClient, MiceliaServiceClient
from app.sdk.models import EVENT_CHANNELS

# =============================================================================
# Helpers (clonados de test_idm_sdk.py)
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


class _FakeListen:
    """Async-iterator falso para simular ``pubsub.listen()``.

    Emite los mensajes provistos y luego se detiene (StopAsyncIteration).
    """

    def __init__(self, messages):
        self._messages = list(messages)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


# =============================================================================
# __init__ — default URL (L70)
# =============================================================================


class TestDefaultUrl:
    def test_default_micelia_url_when_all_none(self):
        """Sin micelia_url ni idm_core_url → default localhost:8888."""
        c = IdmServiceClient(
            service_name="s", port=1, category="health", micelia_url=None
        )
        assert c.micelia_url == "http://localhost:8888"


# =============================================================================
# start() completo — redis + heartbeat (L112, L119)
# =============================================================================


class TestStartFull:
    @pytest.mark.asyncio
    async def test_start_connects_redis_and_spawns_heartbeat(self):
        c = _make_client(redis_url="redis://localhost:6379", heartbeat_interval=30)
        with (
            patch.object(c, "_connect_redis", new_callable=AsyncMock) as mock_conn,
            patch.object(c, "register", new_callable=AsyncMock) as mock_reg,
        ):
            mock_reg.return_value = True
            await c.start()

            assert c._http_client is not None
            mock_conn.assert_awaited_once()
            mock_reg.assert_awaited_once()
            assert c._heartbeat_task is not None
            assert not c._heartbeat_task.done()

            await c.stop()
            assert c._http_client.is_closed


# =============================================================================
# stop() con recursos vivos (L131-135, 138-142, 145-146, 149)
# =============================================================================


class TestStopWithLiveResources:
    @pytest.mark.asyncio
    async def test_stop_cancels_tasks_and_closes_redis(self):
        c = _make_client()

        async def _forever():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise

        c._heartbeat_task = asyncio.create_task(_forever())
        c._listener_task = asyncio.create_task(_forever())
        # dar un tick para que las tasks arranquen
        await asyncio.sleep(0)

        c._pubsub = AsyncMock()
        c._redis = AsyncMock()
        c._http_client = AsyncMock()

        await c.stop()

        assert c._heartbeat_task.cancelled()
        assert c._listener_task.cancelled()
        c._pubsub.unsubscribe.assert_awaited_once()
        c._pubsub.close.assert_awaited_once()
        c._redis.close.assert_awaited_once()
        c._http_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_skips_already_done_tasks(self):
        """Si las tasks ya terminaron, no se intenta cancelarlas de nuevo."""
        c = _make_client()

        async def _noop():
            return None

        done_task = asyncio.create_task(_noop())
        await done_task  # asegura done()==True
        c._heartbeat_task = done_task
        c._listener_task = done_task
        c._pubsub = None
        c._redis = None
        c._http_client = None

        await c.stop()  # no debe lanzar
        assert done_task.done()


# =============================================================================
# _heartbeat_loop (L230-238)
# =============================================================================


class TestHeartbeatLoop:
    @pytest.mark.asyncio
    async def test_loop_sends_heartbeat_then_cancelled(self):
        c = _make_client(heartbeat_interval=0)
        beats = []

        async def _fake_heartbeat():
            beats.append(1)
            return True

        with patch.object(c, "heartbeat", side_effect=_fake_heartbeat):
            task = asyncio.create_task(c._heartbeat_loop())
            # dejar correr algunas iteraciones (sleep(0) no bloquea)
            for _ in range(5):
                await asyncio.sleep(0)
            task.cancel()
            await task  # rama CancelledError → break

        assert beats  # al menos un heartbeat enviado

    @pytest.mark.asyncio
    async def test_loop_recovers_from_exception(self):
        """heartbeat lanza → rama except (log + sleep(5)), luego se cancela."""
        c = _make_client(heartbeat_interval=0)
        calls = {"n": 0}

        async def _boom():
            calls["n"] += 1
            raise RuntimeError("boom")

        real_sleep = asyncio.sleep

        async def _fast_sleep(seconds):
            # no esperar los 5s del backoff; sí ceder control
            await real_sleep(0)

        with (
            patch.object(c, "heartbeat", side_effect=_boom),
            patch("app.sdk.client.asyncio.sleep", side_effect=_fast_sleep),
        ):
            task = asyncio.create_task(c._heartbeat_loop())
            for _ in range(5):
                await real_sleep(0)
            task.cancel()
            await task

        assert calls["n"] >= 1


# =============================================================================
# publish_event — rama de error (L298-300)
# =============================================================================


class TestPublishEventError:
    @pytest.mark.asyncio
    async def test_publish_event_returns_none_on_exception(self):
        c = _make_client()
        c._http_client = AsyncMock()
        c._http_client.post = AsyncMock(side_effect=Exception("network down"))

        result = await c.publish_event(
            category="health", action="create", event_type="x.y", payload={"a": 1}
        )
        assert result is None


# =============================================================================
# publish_event_bus — rama de error de redis (L351-353)
# =============================================================================


class TestPublishEventBusError:
    @pytest.mark.asyncio
    async def test_returns_false_when_redis_publish_raises(self):
        c = _make_client()
        c._redis = AsyncMock()
        c._redis.publish = AsyncMock(side_effect=Exception("redis boom"))

        result = await c.publish_event_bus(
            category="health", event_type="vitals.updated", data={"bpm": 70}
        )
        assert result is False


# =============================================================================
# subscribe (L364-382)
# =============================================================================


class TestSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_without_redis_raises(self):
        c = _make_client()
        c._redis = None
        with pytest.raises(RuntimeError, match="Redis not connected"):
            await c.subscribe("health", lambda d: None)

    @pytest.mark.asyncio
    async def test_subscribe_resolves_shorthand_and_starts_listener(self):
        c = _make_client()
        c._redis = AsyncMock()
        c._pubsub = AsyncMock()

        async def _cb(_data):
            return None

        with patch.object(c, "_listen_loop", new_callable=AsyncMock):
            await c.subscribe("health", _cb)

            resolved = EVENT_CHANNELS["health"]  # "idm.health"
            c._pubsub.subscribe.assert_awaited_once_with(resolved)
            assert c._subscriptions[resolved] == [_cb]
            assert c._listener_task is not None

            # segunda suscripción al mismo canal: NO re-subscribe en el pubsub
            async def _cb2(_data):
                return None

            await c.subscribe("health", _cb2)
            c._pubsub.subscribe.assert_awaited_once()  # sigue siendo 1
            assert c._subscriptions[resolved] == [_cb, _cb2]

        # limpiar la listener task creada (patcheada → completa al instante)
        if c._listener_task:
            c._listener_task.cancel()
            try:
                await c._listener_task
            except asyncio.CancelledError:
                pass


# =============================================================================
# _listen_loop (L386-408)
# =============================================================================


class TestListenLoop:
    @pytest.mark.asyncio
    async def test_dispatches_to_async_and_sync_callbacks(self):
        c = _make_client()
        channel = "idm.health"
        got_async = []
        got_sync = []

        async def _async_cb(data):
            got_async.append(data)

        def _sync_cb(data):
            got_sync.append(data)

        def _raising_cb(_data):
            raise ValueError("callback boom")  # rama except → logged, no rompe

        c._subscriptions[channel] = [_async_cb, _sync_cb, _raising_cb]

        payload = {"type": "vitals", "bpm": 60}
        messages = [
            {"type": "subscribe", "channel": channel, "data": 1},  # !=message → skip
            {"type": "message", "channel": channel, "data": json.dumps(payload)},
            {"type": "message", "channel": channel, "data": "not-json"},  # rama raw
        ]
        c._pubsub = MagicMock()
        c._pubsub.listen = MagicMock(return_value=_FakeListen(messages))

        await c._listen_loop()  # el iterador se agota → termina

        # el mensaje válido se parsea; el JSON inválido cae a {"raw": ...} y
        # también se despacha (misma lista de callbacks del canal).
        assert got_async == [payload, {"raw": "not-json"}]
        assert got_sync == [payload, {"raw": "not-json"}]

    @pytest.mark.asyncio
    async def test_listen_loop_swallows_unexpected_exception(self):
        """Un error no-Cancelled en el iterador → rama except genérica (log)."""
        c = _make_client()

        class _Boom:
            def __aiter__(self):
                return self

            async def __anext__(self):
                raise RuntimeError("listen exploded")

        c._pubsub = MagicMock()
        c._pubsub.listen = MagicMock(return_value=_Boom())

        # no debe propagar: la rama except lo registra y retorna
        await c._listen_loop()

    @pytest.mark.asyncio
    async def test_listen_loop_cancelled_is_clean(self):
        c = _make_client()

        class _Blocking:
            def __aiter__(self):
                return self

            async def __anext__(self):
                await asyncio.Event().wait()  # bloquea hasta cancelación

        c._pubsub = MagicMock()
        c._pubsub.listen = MagicMock(return_value=_Blocking())

        task = asyncio.create_task(c._listen_loop())
        await asyncio.sleep(0)
        task.cancel()
        await task  # rama CancelledError → pass, sin propagar
        assert task.cancelled() or task.done()


# =============================================================================
# health_response — uptime con _started_at (L443)
# =============================================================================


class TestHealthUptime:
    def test_uptime_positive_when_started(self):
        from datetime import datetime, timedelta, timezone

        c = _make_client()
        c._started_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        health = c.health_response()
        assert health.uptime_seconds >= 5.0


# =============================================================================
# idm_core_url property deprecada (L478-484, L488-494)
# =============================================================================


class TestIdmCoreUrlProperty:
    def test_getter_warns_and_returns_url(self):
        c = _make_client(micelia_url="http://host:8888")
        with pytest.warns(DeprecationWarning):
            value = c.idm_core_url
        assert value == "http://host:8888"

    def test_setter_warns_and_strips_slash(self):
        c = _make_client()
        with pytest.warns(DeprecationWarning):
            c.idm_core_url = "http://new-host:9000/"
        assert c.micelia_url == "http://new-host:9000"


# =============================================================================
# _connect_redis (L498-519)
# =============================================================================


class TestConnectRedis:
    @pytest.mark.asyncio
    async def test_no_url_early_return(self):
        c = _make_client(redis_url=None)
        await c._connect_redis()  # no-op, no debe lanzar
        assert c._redis is None

    @pytest.mark.asyncio
    async def test_success_sets_redis_and_pubsub(self):
        c = _make_client(redis_url="redis://localhost:6379")
        fake_redis = AsyncMock()
        fake_redis.ping = AsyncMock(return_value=True)
        fake_pubsub = MagicMock()
        fake_redis.pubsub = MagicMock(return_value=fake_pubsub)

        # `import redis.asyncio as aioredis` resuelve el submódulo vía getattr,
        # así que parcheamos `from_url` en el módulo real (no sys.modules).
        with patch("redis.asyncio.from_url", return_value=fake_redis):
            await c._connect_redis()

        assert c._redis is fake_redis
        assert c._pubsub is fake_pubsub
        fake_redis.ping.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_import_error_disables_pubsub(self):
        c = _make_client(redis_url="redis://localhost:6379")
        real_import = __import__

        def _fake_import(name, *args, **kwargs):
            if name == "redis.asyncio":
                raise ImportError("no redis")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_fake_import):
            await c._connect_redis()
        assert c._redis is None

    @pytest.mark.asyncio
    async def test_connection_error_disables_pubsub(self):
        c = _make_client(redis_url="redis://localhost:6379")
        fake_redis = AsyncMock()
        fake_redis.ping = AsyncMock(side_effect=Exception("connection refused"))

        with patch("redis.asyncio.from_url", return_value=fake_redis):
            await c._connect_redis()
        assert c._redis is None
