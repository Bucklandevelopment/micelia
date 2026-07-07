"""Async client for communicating with Micelia."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Optional

import httpx
import redis.asyncio as aioredis

from idm_sdk.config import IdmConfig
from idm_sdk.events import EventBusChannel, EventCategory, create_event


class MiceliaClient:
    """Async client that connects a microservice to Micelia.

    Usage::

        async with MiceliaClient() as client:
            await client.register()
            await client.publish_event("health", "vitals.recorded", {"hr": 72})
    """

    def __init__(self, config: Optional[IdmConfig] = None) -> None:
        self.config = config or IdmConfig()  # type: ignore[call-arg]
        self._http = httpx.AsyncClient(
            base_url=self.config.core_url,
            headers={"X-API-Key": self.config.api_key},
            timeout=httpx.Timeout(30.0),
        )
        self._redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._listener_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._subscriptions: dict[str, list[Callable]] = {}
        self._started_at: float = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Verify connectivity with Micelia and start the heartbeat loop."""
        await self.health_check()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self) -> None:
        """Cancel background tasks, close HTTP and Redis connections."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._pubsub = None

        if self._redis:
            await self._redis.close()
            self._redis = None

        await self._http.aclose()

    async def __aenter__(self) -> MiceliaClient:
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.disconnect()

    # ------------------------------------------------------------------
    # API calls
    # ------------------------------------------------------------------

    async def health_check(self) -> dict:
        """``GET /api/v1/health`` -- public endpoint, no auth required."""
        resp = await self._http.get("/api/v1/health")
        resp.raise_for_status()
        return resp.json()

    async def publish_event(
        self,
        category: str,
        action: str,
        payload: Optional[dict] = None,
        *,
        event_type: str = "sdk",
        metadata: Optional[dict] = None,
        tags: Optional[list[str]] = None,
        subcategory: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> dict:
        """``POST /api/v1/events`` -- publish an event to Micelia's event store."""
        body = create_event(
            category=category,
            action=action,
            source=self.config.service_name,
            event_type=event_type,
            payload=payload,
            metadata=metadata,
            tags=tags,
            subcategory=subcategory,
            correlation_id=correlation_id,
        )
        resp = await self._http.post("/api/v1/events", json=body)
        resp.raise_for_status()
        return resp.json()

    async def register(self) -> dict:
        """Announce this service to Micelia via a system event."""
        return await self.publish_event(
            category=EventCategory.SYSTEM,
            action="service.registered",
            payload={
                "service_name": self.config.service_name,
                "service_port": self.config.service_port,
            },
            event_type="system",
            subcategory="sync",
        )

    async def heartbeat(self) -> dict:
        """Send a heartbeat event to Micelia."""
        return await self.publish_event(
            category=EventCategory.SYSTEM,
            action="service.heartbeat",
            payload={"service_name": self.config.service_name},
            event_type="system",
            subcategory="sync",
        )

    # ------------------------------------------------------------------
    # Redis Pub/Sub subscriptions
    # ------------------------------------------------------------------

    async def _ensure_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self.config.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def subscribe(self, category: str, callback: Callable) -> None:
        """Subscribe to a Micelia event bus channel via Redis Pub/Sub.

        ``callback`` receives the parsed event dict for each message on the
        channel ``idm.{category}``.
        """
        r = await self._ensure_redis()
        if self._pubsub is None:
            self._pubsub = r.pubsub()

        channel = EventBusChannel.for_category(category)
        if channel not in self._subscriptions:
            self._subscriptions[channel] = []
            await self._pubsub.subscribe(channel)

        self._subscriptions[channel].append(callback)

        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen())

    async def _listen(self) -> None:
        """Background listener that dispatches Redis Pub/Sub messages."""
        assert self._pubsub is not None
        try:
            async for message in self._pubsub.listen():
                if message["type"] != "message":
                    continue
                channel = message["channel"]
                try:
                    data = json.loads(message["data"])
                except (json.JSONDecodeError, TypeError):
                    data = {"raw": message["data"]}

                for cb in self._subscriptions.get(channel, []):
                    try:
                        if asyncio.iscoroutinefunction(cb):
                            await cb(data)
                        else:
                            cb(data)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _heartbeat_loop(self) -> None:
        """Periodically send heartbeat events (every 30 s)."""
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await self.heartbeat()
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass


IdmClient = MiceliaClient  # deprecated alias, removible en v0.2
