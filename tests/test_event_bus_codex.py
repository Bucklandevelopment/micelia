"""
Tests for EventBus (app.services.event_bus).

Single external boundary, isolated here (no real Redis, no network):

  - **``redis.asyncio``** — ``event_bus`` does ``import redis.asyncio as redis`` and
    calls ``redis.from_url(...)`` in ``connect``. We patch
    ``app.services.event_bus.redis.from_url`` to hand back a ``MagicMock`` client whose
    async methods (``ping``/``publish``/``close``) are ``AsyncMock`` and whose
    ``pubsub()`` returns a mock PubSub with ``AsyncMock`` ``subscribe``/``unsubscribe``/
    ``close`` and a scriptable ``listen``.
  - **``_listen``** is exercised directly (not via the background task) by pointing the
    mock ``pubsub.listen()`` at a small async generator of scripted messages, so the
    ``async for`` terminates deterministically without a real event loop hang.

``asyncio_mode = auto`` (pyproject) → ``async def test_*`` needs no marker.

Covers:
  - connect (happy: from_url + ping + pubsub + connected; ping raises -> except/not connected)
  - disconnect (with live listener task cancel+swallow; with pubsub+redis; all-None no-op)
  - publish (not connected -> warn+discard; happy -> redis.publish with metadata; raises -> except)
  - subscribe (new channel subscribes + starts listener; existing channel appends, no re-sub;
    running task not double-started)
  - unsubscribe (remove specific callback; remove all; empty -> del + pubsub.unsubscribe;
    unknown channel no-op)
  - _listen (valid JSON -> async + sync callbacks; invalid JSON -> raw fallback; non-message
    ignored; callback raises -> logged, loop continues; CancelledError -> clean exit;
    generic exception -> logged)
  - publish_health/education/security/system_event delegate to publish with the right channel
  - CHANNELS shape
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.event_bus as eb
from app.services.event_bus import EventBus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client():
    """A mock ``redis.asyncio`` client + its PubSub, with async methods stubbed."""
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.close = AsyncMock()
    pubsub.listen = MagicMock()

    client = MagicMock()
    client.ping = AsyncMock(return_value=True)
    client.publish = AsyncMock()
    client.close = AsyncMock()
    client.pubsub = MagicMock(return_value=pubsub)
    return client, pubsub


async def _aiter(items):
    """Async generator yielding ``items`` then stopping (single-use)."""
    for it in items:
        yield it


async def _araise(exc):
    """Async generator that raises ``exc`` on first iteration."""
    if False:  # pragma: no cover - only to make this a generator
        yield
    raise exc


async def _connected_bus(monkeypatch):
    """Build an EventBus, patch ``from_url``, and run ``connect`` to a healthy state."""
    client, pubsub = _make_client()
    monkeypatch.setattr(eb.redis, "from_url", MagicMock(return_value=client))
    bus = EventBus()
    await bus.connect()
    return bus, client, pubsub


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


async def test_connect_happy(monkeypatch):
    client, pubsub = _make_client()
    from_url = MagicMock(return_value=client)
    monkeypatch.setattr(eb.redis, "from_url", from_url)

    bus = EventBus()
    await bus.connect()

    from_url.assert_called_once()
    client.ping.assert_awaited_once()
    assert bus._redis is client
    assert bus._pubsub is pubsub
    assert bus._connected is True


async def test_connect_ping_failure_marks_disconnected(monkeypatch):
    client, _ = _make_client()
    client.ping = AsyncMock(side_effect=RuntimeError("no redis"))
    monkeypatch.setattr(eb.redis, "from_url", MagicMock(return_value=client))

    bus = EventBus()
    await bus.connect()

    assert bus._connected is False


# ---------------------------------------------------------------------------
# disconnect
# ---------------------------------------------------------------------------


async def test_disconnect_cancels_listener_and_closes(monkeypatch):
    bus, client, pubsub = await _connected_bus(monkeypatch)
    # A real, still-running task so the cancel + awaited CancelledError branch runs.
    bus._listener_task = asyncio.create_task(asyncio.sleep(10))
    await asyncio.sleep(0)  # let it start

    await bus.disconnect()

    assert bus._listener_task.cancelled()
    pubsub.unsubscribe.assert_awaited_once()
    pubsub.close.assert_awaited_once()
    client.close.assert_awaited_once()
    assert bus._connected is False


async def test_disconnect_with_nothing_is_noop():
    bus = EventBus()  # no listener task, no pubsub, no redis
    await bus.disconnect()
    assert bus._connected is False


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


async def test_publish_when_disconnected_discards():
    bus = EventBus()  # _connected is False
    await bus.publish("idm.health", {"x": 1})
    # nothing to assert beyond "did not raise"; no redis client exists
    assert bus._redis is None


async def test_publish_happy_wraps_metadata(monkeypatch):
    bus, client, _ = await _connected_bus(monkeypatch)

    await bus.publish("idm.health", {"x": 1})

    client.publish.assert_awaited_once()
    channel, payload = client.publish.await_args.args
    assert channel == "idm.health"
    message = json.loads(payload)
    assert message["channel"] == "idm.health"
    assert message["data"] == {"x": 1}
    assert "timestamp" in message


async def test_publish_swallows_redis_error(monkeypatch):
    bus, client, _ = await _connected_bus(monkeypatch)
    client.publish = AsyncMock(side_effect=Exception("boom"))

    # Must not raise — error path only logs.
    await bus.publish("idm.system", {"k": "v"})


# ---------------------------------------------------------------------------
# subscribe
# ---------------------------------------------------------------------------


async def test_subscribe_new_channel_subscribes_and_starts_listener(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    pubsub.listen.return_value = _aiter([])  # listener finishes immediately

    async def cb(_data):
        pass

    await bus.subscribe("idm.ai", cb)

    pubsub.subscribe.assert_awaited_once_with("idm.ai")
    assert bus._subscriptions["idm.ai"] == [cb]
    assert bus._listener_task is not None
    await asyncio.sleep(0)  # drain the (empty) listener task


async def test_subscribe_existing_channel_appends_without_resubscribe(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    pubsub.listen.return_value = _aiter([])

    async def cb1(_data):
        pass

    async def cb2(_data):
        pass

    await bus.subscribe("idm.ai", cb1)
    pubsub.subscribe.reset_mock()
    await bus.subscribe("idm.ai", cb2)  # same channel

    pubsub.subscribe.assert_not_awaited()
    assert bus._subscriptions["idm.ai"] == [cb1, cb2]
    await asyncio.sleep(0)


async def test_subscribe_does_not_double_start_running_listener(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    pubsub.listen.return_value = _aiter([])
    running = asyncio.create_task(asyncio.sleep(10))
    bus._listener_task = running  # not done -> must be reused

    async def cb(_data):
        pass

    await bus.subscribe("idm.ai", cb)

    assert bus._listener_task is running
    running.cancel()
    try:
        await running
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# unsubscribe
# ---------------------------------------------------------------------------


async def test_unsubscribe_specific_callback_keeps_others(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)

    def cb1(_data):
        pass

    def cb2(_data):
        pass

    bus._subscriptions["idm.ai"] = [cb1, cb2]
    await bus.unsubscribe("idm.ai", cb1)

    assert bus._subscriptions["idm.ai"] == [cb2]
    pubsub.unsubscribe.assert_not_awaited()


async def test_unsubscribe_last_callback_removes_channel(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)

    def cb(_data):
        pass

    bus._subscriptions["idm.ai"] = [cb]
    await bus.unsubscribe("idm.ai", cb)

    assert "idm.ai" not in bus._subscriptions
    pubsub.unsubscribe.assert_awaited_once_with("idm.ai")


async def test_unsubscribe_all_callbacks(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    bus._subscriptions["idm.ai"] = [lambda d: None, lambda d: None]

    await bus.unsubscribe("idm.ai")  # callback=None -> drop all

    assert "idm.ai" not in bus._subscriptions
    pubsub.unsubscribe.assert_awaited_once_with("idm.ai")


async def test_unsubscribe_unknown_channel_is_noop():
    bus = EventBus()
    await bus.unsubscribe("idm.nope")  # no KeyError
    assert bus._subscriptions == {}


# ---------------------------------------------------------------------------
# _listen
# ---------------------------------------------------------------------------


async def test_listen_dispatches_to_async_and_sync_callbacks(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    got = []

    async def async_cb(data):
        got.append(("async", data))

    def sync_cb(data):
        got.append(("sync", data))

    bus._subscriptions["c"] = [async_cb, sync_cb]
    pubsub.listen.return_value = _aiter(
        [
            {"type": "message", "channel": "c", "data": json.dumps({"a": 1})},
            {"type": "subscribe", "channel": "c", "data": 1},  # ignored (not a message)
        ]
    )

    await bus._listen()

    assert ("async", {"a": 1}) in got
    assert ("sync", {"a": 1}) in got


async def test_listen_invalid_json_uses_raw_fallback(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    got = []

    async def cb(data):
        got.append(data)

    bus._subscriptions["c"] = [cb]
    pubsub.listen.return_value = _aiter(
        [{"type": "message", "channel": "c", "data": "not-json"}]
    )

    await bus._listen()

    assert got == [{"raw": "not-json"}]


async def test_listen_callback_error_is_swallowed(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)

    async def boom(_data):
        raise RuntimeError("callback failed")

    bus._subscriptions["c"] = [boom]
    pubsub.listen.return_value = _aiter(
        [{"type": "message", "channel": "c", "data": json.dumps({"a": 1})}]
    )

    # Loop keeps going / does not raise.
    await bus._listen()


async def test_listen_cancelled_exits_cleanly(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    pubsub.listen.return_value = _araise(asyncio.CancelledError())

    await bus._listen()  # CancelledError caught internally, no raise


async def test_listen_generic_exception_is_logged(monkeypatch):
    bus, _, pubsub = await _connected_bus(monkeypatch)
    pubsub.listen.return_value = _araise(RuntimeError("stream broke"))

    await bus._listen()  # generic except branch, no raise


# ---------------------------------------------------------------------------
# convenience publishers + CHANNELS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method, channel",
    [
        ("publish_health_event", "idm.health"),
        ("publish_education_event", "idm.education"),
        ("publish_security_event", "idm.security"),
        ("publish_system_event", "idm.system"),
    ],
)
async def test_convenience_publishers_delegate(method, channel):
    bus = EventBus()
    bus.publish = AsyncMock()  # type: ignore[method-assign]

    await getattr(bus, method)("created", {"id": 7})

    bus.publish.assert_awaited_once_with(channel, {"type": "created", "id": 7})


def test_channels_shape():
    assert EventBus.CHANNELS["health"] == "idm.health"
    assert EventBus.CHANNELS["prompts"] == "idm.prompts"
    assert len(EventBus.CHANNELS) == 8
    assert all(v.startswith("idm.") for v in EventBus.CHANNELS.values())
