"""
IdmServiceClient: Main SDK client for microservice integration with Micelia.

Provides:
- Service registration with Micelia gateway
- Periodic heartbeat / health reporting
- Event publishing to the Event Store (REST) and Event Bus (Redis pub/sub)
- Event subscription via Redis pub/sub
- Standardized health check response generation
"""

import asyncio
import json
import logging
import warnings
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import httpx

from app.sdk.models import EVENT_CHANNELS, HealthResponse, IdmEvent

if TYPE_CHECKING:
    import redis.asyncio as aioredis

logger = logging.getLogger("micelia-sdk")


class IdmServiceClient:
    """
    Lightweight client that microservices use to integrate with Micelia.

    Args:
        service_name: Unique name of this microservice (e.g. "biohack-app").
        port: Port this microservice listens on.
        category: Service category ("health", "education", "research", "security").
        micelia_url: Base URL of the Micelia gateway. Accepts deprecated
            kwarg ``idm_core_url`` as alias (will emit DeprecationWarning).
        api_key: API key for authenticating with Micelia.
        version: Version string of this microservice.
        capabilities: List of capability tags (e.g. ["healthkit", "ml"]).
        heartbeat_interval: Seconds between heartbeat pings (0 to disable).
        redis_url: Redis URL for pub/sub (None to use REST-only mode).
    """

    def __init__(
        self,
        service_name: str,
        port: int,
        category: str,
        micelia_url: Optional[str] = None,
        api_key: str = "",
        version: str = "0.1.0",
        capabilities: Optional[List[str]] = None,
        heartbeat_interval: int = 30,
        redis_url: Optional[str] = None,
        *,
        idm_core_url: Optional[str] = None,  # deprecated alias
    ):
        if idm_core_url is not None:
            warnings.warn(
                "El kwarg `idm_core_url` está deprecado, usa `micelia_url`. "
                "Será removido en v0.2.",
                DeprecationWarning,
                stacklevel=2,
            )
            if micelia_url is None:
                micelia_url = idm_core_url
        if micelia_url is None:
            micelia_url = "http://localhost:8888"

        self.service_name = service_name
        self.port = port
        self.category = category
        self.micelia_url = micelia_url.rstrip("/")
        self.api_key = api_key
        self.version = version
        self.capabilities = capabilities or []
        self.heartbeat_interval = heartbeat_interval
        self.redis_url = redis_url

        # Resource attributes are non-None after start()/_connect_redis();
        # annotate with concrete runtime types (contract), init to None.
        self._http_client: httpx.AsyncClient = None  # type: ignore[assignment]
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._redis: "aioredis.Redis" = None  # type: ignore[assignment]
        self._pubsub: "aioredis.client.PubSub" = None  # type: ignore[assignment]
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._started_at: Optional[datetime] = None
        self._healthy = True
        self._last_error: Optional[str] = None

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def start(self):
        """
        Initialize the client: create HTTP client, register with Micelia,
        and start the background heartbeat.
        """
        self._started_at = datetime.now(timezone.utc)

        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            headers=self._auth_headers(),
        )

        # Connect to Redis if URL provided
        if self.redis_url:
            await self._connect_redis()

        # Register with Micelia
        await self.register()

        # Start heartbeat
        if self.heartbeat_interval > 0:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(
            "micelia-sdk started: service=%s port=%d category=%s",
            self.service_name,
            self.port,
            self.category,
        )

    async def stop(self):
        """Gracefully shut down the client."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()

        if self._redis:
            await self._redis.close()

        if self._http_client:
            await self._http_client.aclose()

        logger.info("micelia-sdk stopped: service=%s", self.service_name)

    # =========================================================================
    # Registration
    # =========================================================================

    async def register(self) -> bool:
        """
        Register this microservice with Micelia.

        Sends a POST to Micelia with service metadata so the gateway
        knows how to route traffic and monitor health.
        """
        payload = {
            "service_name": self.service_name,
            "port": self.port,
            "category": self.category,
            "version": self.version,
            "capabilities": self.capabilities,
            "health_endpoint": "/health",
            "status": "starting",
        }

        try:
            response = await self._http_client.post(
                f"{self.micelia_url}/api/v1/events",
                json={
                    "category": "system",
                    "source": self.service_name,
                    "action": "create",
                    "event_type": "service.registered",
                    "payload": payload,
                    "metadata": {"sdk_version": "1.0.0"},
                    "tags": ["registration"],
                },
            )
            if response.status_code in (200, 201):
                logger.info("Registered with Micelia: %s", self.service_name)
                return True
            else:
                logger.warning(
                    "Registration returned %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                return False
        except Exception as e:
            logger.warning("Could not register with Micelia: %s", e)
            return False

    # =========================================================================
    # Heartbeat
    # =========================================================================

    async def heartbeat(self) -> bool:
        """Send a single heartbeat to Micelia with current health status."""
        health = self.health_response()
        try:
            response = await self._http_client.post(
                f"{self.micelia_url}/api/v1/events",
                json={
                    "category": "system",
                    "source": self.service_name,
                    "action": "update",
                    "event_type": "service.heartbeat",
                    "payload": health.to_dict(),
                    "tags": ["heartbeat"],
                },
            )
            return response.status_code in (200, 201)
        except Exception as e:
            logger.debug("Heartbeat failed: %s", e)
            return False

    async def _heartbeat_loop(self):
        """Background loop that sends periodic heartbeats."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self.heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Heartbeat loop error: %s", e)
                await asyncio.sleep(5)

    # =========================================================================
    # Events (REST)
    # =========================================================================

    async def publish_event(
        self,
        category: str,
        action: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        subcategory: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        correlation_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Publish an event to Micelia's Event Store via REST API.

        Args:
            category: Event category (health, education, research, security, system).
            action: Action type (create, update, delete, query, analyze).
            event_type: Specific event type (e.g. "biomarker.recorded").
            payload: Event data.
            subcategory: Optional sub-category.
            metadata: Optional metadata.
            tags: Optional tags.
            correlation_id: Optional correlation ID to group related events.

        Returns:
            Event ID string if successful, None otherwise.
        """
        event = IdmEvent(
            category=category,
            source=self.service_name,
            action=action,
            event_type=event_type,
            payload=payload or {},
            subcategory=subcategory,
            metadata=metadata or {},
            tags=tags or [],
            correlation_id=correlation_id,
        )

        try:
            response = await self._http_client.post(
                f"{self.micelia_url}/api/v1/events",
                json=event.to_dict(),
            )
            if response.status_code in (200, 201):
                data = response.json()
                return data.get("event_id")
            else:
                logger.warning(
                    "publish_event returned %d: %s",
                    response.status_code,
                    response.text[:200],
                )
                return None
        except Exception as e:
            logger.error("Failed to publish event: %s", e)
            return None

    # =========================================================================
    # Events (Redis Pub/Sub)
    # =========================================================================

    async def publish_event_bus(
        self,
        category: str,
        event_type: str,
        data: Dict[str, Any],
    ) -> bool:
        """
        Publish an event directly to the Redis Event Bus.

        This bypasses the REST API and publishes directly to Redis pub/sub
        for low-latency inter-service communication.

        Args:
            category: Event category (maps to a Redis channel).
            event_type: Event type string.
            data: Event payload.

        Returns:
            True if published successfully.
        """
        if not self._redis:
            logger.warning("Redis not connected; falling back to REST")
            event_id = await self.publish_event(
                category=category,
                action="create",
                event_type=event_type,
                payload=data,
            )
            return event_id is not None

        channel = EVENT_CHANNELS.get(category, f"idm.{category}")
        message = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "channel": channel,
            "data": {
                "type": event_type,
                "source": self.service_name,
                **data,
            },
        }

        try:
            await self._redis.publish(channel, json.dumps(message))
            logger.debug("Published to %s: %s", channel, event_type)
            return True
        except Exception as e:
            logger.error("Redis publish failed: %s", e)
            return False

    async def subscribe(self, channel: str, callback: Callable) -> None:
        """
        Subscribe to events on a Redis pub/sub channel.

        Args:
            channel: Channel name (e.g. "idm.health") or category shorthand
                     (e.g. "health" which maps to "idm.health").
            callback: Async function that receives the parsed event dict.
        """
        if not self._redis:
            raise RuntimeError(
                "Redis not connected. Provide redis_url to IdmServiceClient."
            )

        # Map shorthand to full channel name
        resolved = EVENT_CHANNELS.get(channel, channel)

        if resolved not in self._subscriptions:
            self._subscriptions[resolved] = []
            await self._pubsub.subscribe(resolved)

        self._subscriptions[resolved].append(callback)

        # Start listener if not running
        if not self._listener_task or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen_loop())

        logger.info("Subscribed to channel: %s", resolved)

    async def _listen_loop(self):
        """Background loop that dispatches incoming pub/sub messages."""
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
                    except Exception as e:
                        logger.error("Subscription callback error on %s: %s", channel, e)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Listener loop error: %s", e)

    # =========================================================================
    # Health
    # =========================================================================

    def health_response(
        self,
        dependencies: Optional[Dict[str, str]] = None,
        status_override: Optional[str] = None,
    ) -> HealthResponse:
        """
        Generate a standardized health check response.

        Args:
            dependencies: Map of dependency name to status string
                          (e.g. {"postgresql": "healthy", "redis": "degraded"}).
            status_override: Force a specific status instead of auto-detecting.

        Returns:
            HealthResponse dataclass with all fields populated.
        """
        deps = dependencies or {}

        if status_override:
            status = status_override
        elif not self._healthy:
            status = "unhealthy"
        elif any(v == "unhealthy" for v in deps.values()):
            status = "degraded"
        else:
            status = "healthy"

        uptime = 0.0
        if self._started_at:
            uptime = (datetime.now(timezone.utc) - self._started_at).total_seconds()

        return HealthResponse(
            status=status,
            version=self.version,
            service=self.service_name,
            category=self.category,
            port=self.port,
            capabilities=self.capabilities,
            uptime_seconds=round(uptime, 1),
            dependencies=deps,
        )

    def set_healthy(self, healthy: bool, error: Optional[str] = None):
        """Update the health status of this service."""
        self._healthy = healthy
        self._last_error = error

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _auth_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    # =========================================================================
    # Deprecated compat properties
    # =========================================================================

    @property
    def idm_core_url(self) -> str:
        """Deprecated alias for ``self.micelia_url``. Removible en v0.2."""
        warnings.warn(
            "`idm_core_url` está deprecado, usa `micelia_url`. "
            "Será removido en v0.2.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.micelia_url

    @idm_core_url.setter
    def idm_core_url(self, value: str) -> None:
        warnings.warn(
            "`idm_core_url` está deprecado, usa `micelia_url`. "
            "Será removido en v0.2.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.micelia_url = value.rstrip("/")

    async def _connect_redis(self):
        """Connect to Redis for pub/sub."""
        if not self.redis_url:
            return
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self._redis.ping()  # type: ignore[misc]
            self._pubsub = self._redis.pubsub()
            logger.info("Redis connected: %s", self.redis_url)
        except ImportError:
            logger.warning(
                "redis package not installed; pub/sub disabled. "
                "Install with: pip install redis"
            )
            self._redis = None  # type: ignore[assignment]
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
            self._redis = None  # type: ignore[assignment]
