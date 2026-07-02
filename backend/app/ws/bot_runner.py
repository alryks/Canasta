"""Drives bot turns automatically once it's their turn.

A bot has no real WebSocket -- instead, after anything that might hand the
turn to one (game start, any intent, a host force-skip), `router.py` calls
`maybe_schedule_bot_turn` with the session/game/game_state it already has in
hand. If the new current player is a bot, this schedules a background step
that waits a beat, decides one intent via the bot's strategy, and feeds it
through the exact same `_handle_intent` real WS messages go through -- which
itself calls `maybe_schedule_bot_turn` again at the end. That's the whole
loop: no explicit while-loop here, it's just recursion through the normal
intent-handling path, so multiple bots in a row (or a bot's own
draw-then-discard) chain automatically.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.strategy import BOT_STRATEGIES, DEFAULT_BOT_STRATEGY
from app.db.models import Game, Player
from app.engine.engine import GameState
from app.redis_store import RedisGameStore

BOT_MOVE_DELAY_SECONDS = 1.2  # cosmetic pause so a bot's turn doesn't feel instant

store = RedisGameStore()


async def maybe_schedule_bot_turn(
    session: AsyncSession, game: Game, game_state: GameState
) -> None:
    """Reuses the caller's already-open session for the cheap "is the next
    player a bot" check instead of opening a second one -- a real Postgres
    deployment tolerates concurrent sessions fine, but nesting one inside a
    still-open caller session trips up the in-memory SQLite used in tests."""
    if game_state.current_deal is None:
        return
    bot_id = game_state.current_deal.turn_state.current_player_id
    player = await session.get(Player, bot_id)
    if player is None or not player.is_bot:
        return

    asyncio.create_task(_play_bot_step(game.id, bot_id))


async def _play_bot_step(game_id: str, bot_id: str) -> None:
    await asyncio.sleep(BOT_MOVE_DELAY_SECONDS)

    game_state = store.get_state(game_id)
    if game_state is None or game_state.current_deal is None:
        return
    if game_state.current_deal.turn_state.current_player_id != bot_id:
        return  # turn moved on (e.g. a host skip raced this step) -- nothing to do

    strategy = BOT_STRATEGIES[DEFAULT_BOT_STRATEGY]
    intent, data = strategy.choose_intent(game_state.current_deal, bot_id)

    # Deferred import: router.py calls maybe_schedule_bot_turn, so importing
    # it at module load time here would be circular.
    from app.ws.router import _handle_intent

    await _handle_intent(game_id, bot_id, {"type": intent, "data": data})
