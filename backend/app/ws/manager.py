"""In-memory WS connection registry, keyed by game_id -> player_id.

Redis pub/sub for cross-worker fanout (plan section 10) is deferred until
horizontal scaling is actually needed -- NFR-5 explicitly targets a single
instance at this scale, so a second broadcast path would be premature.
"""

from __future__ import annotations

from typing import Callable

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[str, WebSocket]] = {}

    def register(self, game_id: str, player_id: str, websocket: WebSocket) -> None:
        self._connections.setdefault(game_id, {})[player_id] = websocket

    def unregister(self, game_id: str, player_id: str) -> None:
        self._connections.get(game_id, {}).pop(player_id, None)

    def connected_player_ids(self, game_id: str) -> list[str]:
        return list(self._connections.get(game_id, {}).keys())

    async def send_to(self, game_id: str, player_id: str, message: dict) -> None:
        ws = self._connections.get(game_id, {}).get(player_id)
        if ws is not None:
            await ws.send_json(message)

    async def broadcast(self, game_id: str, message: dict) -> None:
        for ws in list(self._connections.get(game_id, {}).values()):
            await ws.send_json(message)

    async def broadcast_personalized(
        self, game_id: str, build_message: Callable[[str], dict]
    ) -> None:
        for player_id, ws in list(self._connections.get(game_id, {}).items()):
            await ws.send_json(build_message(player_id))


manager = ConnectionManager()
