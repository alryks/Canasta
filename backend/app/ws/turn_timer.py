"""In-memory turn timeout (plan section 15, FR-35/36/37).

Ephemeral and single-instance-local, mirroring `app.ws.manager` -- it just
needs to notice "the current player is gone" and give the host a grace
period before their manual skip-with-penalty button is allowed. Nothing
here is persisted: a server restart simply forgets in-flight timers, which
is fine since the underlying GameState in Redis is unaffected either way.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

TURN_TIMEOUT_SECONDS = 90.0

_tasks: dict[str, tuple[asyncio.Task, str]] = {}
_expired: dict[str, str] = {}


def expired_player(game_id: str) -> str | None:
    """The player whose turn timed out and is awaiting a host skip, if any."""
    return _expired.get(game_id)


async def _run(
    game_id: str, player_id: str, on_expire: Callable[[], Awaitable[None]]
) -> None:
    try:
        await asyncio.sleep(TURN_TIMEOUT_SECONDS)
    except asyncio.CancelledError:
        return
    _expired[game_id] = player_id
    _tasks.pop(game_id, None)
    await on_expire()


def arm(game_id: str, player_id: str, on_expire: Callable[[], Awaitable[None]]) -> None:
    """Start a timeout for `player_id`'s turn, unless one is already running
    for this exact game+player pair."""
    entry = _tasks.get(game_id)
    if entry is not None and entry[1] == player_id:
        return
    if entry is not None:
        entry[0].cancel()
    task = asyncio.create_task(_run(game_id, player_id, on_expire))
    _tasks[game_id] = (task, player_id)
    _expired.pop(game_id, None)


def cancel_for_player(game_id: str, player_id: str) -> None:
    """Cancel the running/expired timeout, but only if it belongs to
    `player_id` -- a reconnect from an unrelated player must not clear
    someone else's legitimate timeout."""
    entry = _tasks.get(game_id)
    if entry is not None and entry[1] == player_id:
        entry[0].cancel()
        _tasks.pop(game_id, None)
    if _expired.get(game_id) == player_id:
        _expired.pop(game_id, None)


def cancel_game(game_id: str) -> None:
    """Full cleanup once a game can no longer take turns (e.g. game_over)."""
    entry = _tasks.pop(game_id, None)
    if entry is not None:
        entry[0].cancel()
    _expired.pop(game_id, None)
