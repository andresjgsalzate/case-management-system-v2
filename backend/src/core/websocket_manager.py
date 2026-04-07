import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Gestiona WebSockets locales + Redis pub/sub para escalar entre workers.
    Canal Redis por caso: "ws:case:{case_id}"

    Arquitectura: cada worker mantiene su propio dict de conexiones locales.
    Cuando un mensaje llega via REST o WS, se publica en Redis para que TODOS
    los workers lo reenvíen a sus conexiones locales — garantizando que usuarios
    en diferentes workers del mismo caso reciben el mensaje.
    """

    def __init__(self) -> None:
        # { case_id: { user_id: WebSocket } }
        self.active_connections: dict[str, dict[str, WebSocket]] = {}

    async def connect(self, case_id: str, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if case_id not in self.active_connections:
            self.active_connections[case_id] = {}
        self.active_connections[case_id][user_id] = websocket

    def disconnect(self, case_id: str, user_id: str) -> None:
        if case_id in self.active_connections:
            self.active_connections[case_id].pop(user_id, None)
            if not self.active_connections[case_id]:
                del self.active_connections[case_id]

    async def broadcast_local(self, case_id: str, message: dict[str, Any]) -> None:
        """Envía a todos los WS locales conectados al caso. Limpia conexiones muertas."""
        connections = self.active_connections.get(case_id, {})
        dead: list[str] = []
        for uid, ws in connections.items():
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(uid)
        for uid in dead:
            self.disconnect(case_id, uid)

    async def publish_to_redis(self, case_id: str, message: dict[str, Any]) -> None:
        """Publica en Redis para que otros workers también reciban el mensaje."""
        try:
            from backend.src.core.redis_client import get_redis
            redis = get_redis()
            channel = f"ws:case:{case_id}"
            await redis.publish(channel, json.dumps(message))
        except Exception as e:
            logger.warning(f"Redis publish failed for case {case_id}: {e}")

    async def broadcast(self, case_id: str, message: dict[str, Any]) -> None:
        """Envía localmente Y publica en Redis para otros workers."""
        await self.broadcast_local(case_id, message)
        await self.publish_to_redis(case_id, message)

    async def subscribe_and_forward(self, case_id: str) -> None:
        """
        Loop de suscripción Redis → forward a WS locales.
        Se inicia como background task al primer connect de un caso.
        """
        try:
            from backend.src.core.redis_client import get_redis
            redis = get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe(f"ws:case:{case_id}")
            try:
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        data = json.loads(msg["data"])
                        await self.broadcast_local(case_id, data)
            except asyncio.CancelledError:
                await pubsub.unsubscribe(f"ws:case:{case_id}")
        except Exception as e:
            logger.warning(f"Redis subscribe failed for case {case_id}: {e}")


# Singleton global — compartido por todos los endpoints del proceso
manager = ConnectionManager()
