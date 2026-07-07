"""
Event Bus: Sistema de mensajería Pub/Sub basado en Redis.

Permite comunicación asíncrona entre servicios del Panel IDM.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import log


class EventBus:
    """
    Bus de eventos basado en Redis Pub/Sub.

    Permite que los servicios publiquen y suscriban a eventos en tiempo real.
    """

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect(self):
        """Conecta al servidor Redis"""
        try:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )

            # Verificar conexión
            await self._redis.ping()

            self._pubsub = self._redis.pubsub()
            self._connected = True

            log.info(f"Event Bus conectado a Redis: {settings.redis_url}")

        except Exception as e:
            log.error(f"Error conectando a Redis: {e}")
            self._connected = False

    async def disconnect(self):
        """Desconecta del servidor Redis"""
        if self._listener_task:
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

        self._connected = False
        log.info("Event Bus desconectado")

    async def publish(self, channel: str, event: dict):
        """
        Publica un evento en un canal.

        Args:
            channel: Nombre del canal (ej: "idm.health", "idm.education")
            event: Diccionario con datos del evento
        """
        if not self._connected:
            log.warning("Event Bus no conectado, evento descartado")
            return

        try:
            # Añadir metadata
            message = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "channel": channel,
                "data": event
            }

            await self._redis.publish(channel, json.dumps(message))
            log.debug(f"Evento publicado en {channel}")

        except Exception as e:
            log.error(f"Error publicando evento: {e}")

    async def subscribe(self, channel: str, callback: Callable):
        """
        Suscribe a un canal con un callback.

        Args:
            channel: Nombre del canal
            callback: Función async que recibe el evento
        """
        if channel not in self._subscriptions:
            self._subscriptions[channel] = []
            if self._pubsub:
                await self._pubsub.subscribe(channel)

        self._subscriptions[channel].append(callback)

        # Iniciar listener si no está corriendo
        if not self._listener_task or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._listen())

        log.info(f"Suscrito a canal: {channel}")

    async def unsubscribe(self, channel: str, callback: Callable = None):
        """
        Desuscribe de un canal.

        Args:
            channel: Nombre del canal
            callback: Callback específico a remover (None = todos)
        """
        if channel in self._subscriptions:
            if callback:
                self._subscriptions[channel].remove(callback)
            else:
                self._subscriptions[channel] = []

            if not self._subscriptions[channel]:
                del self._subscriptions[channel]
                if self._pubsub:
                    await self._pubsub.unsubscribe(channel)

    async def _listen(self):
        """Escucha mensajes de los canales suscritos"""
        try:
            async for message in self._pubsub.listen():
                if message["type"] == "message":
                    channel = message["channel"]
                    try:
                        data = json.loads(message["data"])
                    except json.JSONDecodeError:
                        data = {"raw": message["data"]}

                    # Llamar callbacks suscritos
                    if channel in self._subscriptions:
                        for callback in self._subscriptions[channel]:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(data)
                                else:
                                    callback(data)
                            except Exception as e:
                                log.error(f"Error en callback de {channel}: {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Error en listener: {e}")

    # =========================================================================
    # Canales predefinidos del Panel IDM
    # =========================================================================

    CHANNELS = {
        "health": "idm.health",
        "education": "idm.education",
        "identity": "idm.identity",
        "security": "idm.security",
        "system": "idm.system",
        "ai": "idm.ai",
        "energy": "idm.energy",
        "prompts": "idm.prompts"
    }

    async def publish_health_event(self, event_type: str, data: dict):
        """Publica evento de salud"""
        await self.publish(self.CHANNELS["health"], {
            "type": event_type,
            **data
        })

    async def publish_education_event(self, event_type: str, data: dict):
        """Publica evento de educación"""
        await self.publish(self.CHANNELS["education"], {
            "type": event_type,
            **data
        })

    async def publish_security_event(self, event_type: str, data: dict):
        """Publica evento de seguridad"""
        await self.publish(self.CHANNELS["security"], {
            "type": event_type,
            **data
        })

    async def publish_system_event(self, event_type: str, data: dict):
        """Publica evento del sistema"""
        await self.publish(self.CHANNELS["system"], {
            "type": event_type,
            **data
        })
