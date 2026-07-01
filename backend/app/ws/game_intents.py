"""In-deal WS intents (plan section 8, phase 4): draw/meld/steal/discard.

Dispatches onto the pure engine (apply_action) against the live GameState
kept in Redis. Discard/concede_penalty and deal scoring land in the next
step -- this one wires up draw_deck/draw_discard/create_meld/add_to_meld/
steal_wild.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game
from app.engine.actions import (
    Action,
    AddToMeld,
    CreateMeld,
    DrawDeck,
    DrawDiscard,
    StealWild,
)
from app.engine.engine import GameState, apply_action
from app.engine.errors import IllegalActionError
from app.redis_store import RedisGameStore

GAME_INTENTS = frozenset(
    {"draw_deck", "draw_discard", "create_meld", "add_to_meld", "steal_wild"}
)


@dataclass
class GameIntentResult:
    game_state: GameState
    deal_completed: bool
    deal_result_message: dict | None
    winner_team_id: str | None


def _build_action(intent: str, data: dict) -> Action:
    if intent == "draw_deck":
        return DrawDeck()
    if intent == "draw_discard":
        return DrawDiscard()
    if intent == "create_meld":
        return CreateMeld(card_ids=list(data.get("card_ids", [])))
    if intent == "add_to_meld":
        return AddToMeld(
            meld_id=data.get("meld_id", ""), card_ids=list(data.get("card_ids", []))
        )
    if intent == "steal_wild":
        return StealWild(
            meld_id=data.get("meld_id", ""),
            wild_card_id=data.get("wild_card_id", ""),
            replacement_card_id=data.get("replacement_card_id", ""),
        )
    raise IllegalActionError(f"unknown intent {intent!r}")


async def apply_game_intent(
    store: RedisGameStore,
    session: AsyncSession,
    game: Game,
    sender_id: str,
    intent: str,
    data: dict,
) -> GameIntentResult:
    if game.status != "IN_PROGRESS":
        raise IllegalActionError("game is not in progress")

    action = _build_action(intent, data)

    with store.lock(game.id):
        game_state = store.get_state(game.id)
        if game_state is None or game_state.current_deal is None:
            raise IllegalActionError("no active deal")

        apply_action(game_state.current_deal, sender_id, action)
        store.set_state(game.id, game_state)

    return GameIntentResult(
        game_state=game_state,
        deal_completed=False,
        deal_result_message=None,
        winner_team_id=None,
    )
