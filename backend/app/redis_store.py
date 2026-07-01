"""Redis wrapper: get/set GameState, per-game lock (plan section 10)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from collections.abc import Iterator

import redis

from app.config import settings
from app.engine.engine import GameState
from app.engine.serialization import game_state_from_dict, game_state_to_dict

LOCK_TIMEOUT_SECONDS = 10
LOCK_BLOCKING_TIMEOUT_SECONDS = 5


def _state_key(game_id: str) -> str:
    return f"game:{game_id}:state"


def _lock_key(game_id: str) -> str:
    return f"game:{game_id}:lock"


def _events_channel(game_id: str) -> str:
    return f"game:{game_id}:events"


class RedisGameStore:
    def __init__(self, client: redis.Redis | None = None) -> None:
        self.client = client or redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )

    def get_state(self, game_id: str) -> GameState | None:
        raw = self.client.get(_state_key(game_id))
        if raw is None:
            return None
        return game_state_from_dict(json.loads(raw))

    def set_state(self, game_id: str, game_state: GameState) -> None:
        payload = json.dumps(game_state_to_dict(game_state))
        self.client.set(_state_key(game_id), payload)

    def delete_state(self, game_id: str) -> None:
        self.client.delete(_state_key(game_id))

    @contextmanager
    def lock(
        self,
        game_id: str,
        *,
        timeout: float = LOCK_TIMEOUT_SECONDS,
        blocking_timeout: float = LOCK_BLOCKING_TIMEOUT_SECONDS,
    ) -> Iterator[None]:
        """Mutex around processing a single action for this game (NFR-4)."""
        with self.client.lock(
            _lock_key(game_id),
            timeout=timeout,
            blocking_timeout=blocking_timeout,
        ):
            yield

    def publish_event(self, game_id: str, message: str) -> None:
        self.client.publish(_events_channel(game_id), message)
