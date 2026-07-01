"""In-deal WS intents (plan section 8, phase 4): draw/meld/steal/discard.

Dispatches onto the pure engine (apply_action) against the live GameState
kept in Redis, then -- if the action ended the deal -- scores it, persists
the Deal row, and either starts the next deal or finishes the game.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Deal as DealRow
from app.db.models import Game, Player
from app.engine.actions import (
    Action,
    AddToMeld,
    ConcedePenalty,
    CreateMeld,
    Discard,
    DrawDeck,
    DrawDiscard,
    StealWild,
)
from app.engine.engine import (
    DealSummary,
    GameState,
    apply_action,
    final_deal_scores,
    start_new_deal,
)
from app.engine.errors import IllegalActionError
from app.redis_store import RedisGameStore

GAME_INTENTS = frozenset(
    {
        "draw_deck",
        "draw_discard",
        "create_meld",
        "add_to_meld",
        "steal_wild",
        "discard",
        "concede_penalty",
    }
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
    if intent == "discard":
        return Discard(card_id=data.get("card_id", ""))
    if intent == "concede_penalty":
        return ConcedePenalty()
    raise IllegalActionError(f"unknown intent {intent!r}")


async def _complete_deal(
    session: AsyncSession, game: Game, game_state: GameState
) -> tuple[dict, str | None]:
    deal = game_state.current_deal
    assert deal is not None

    breakdowns = final_deal_scores(deal)
    for team_id, breakdown in breakdowns.items():
        game_state.scores[team_id] = game_state.scores.get(team_id, 0) + breakdown.total

    deal_number = game.current_deal_number
    score_breakdown = {tid: asdict(b) for tid, b in breakdowns.items()}
    team_scores_after = dict(game_state.scores)

    session.add(
        DealRow(
            game_id=game.id,
            deal_number=deal_number,
            score_breakdown=score_breakdown,
            team_scores_after=team_scores_after,
        )
    )
    game_state.deal_history.append(
        DealSummary(
            deal_number=deal_number,
            score_breakdown=score_breakdown,
            team_scores_after=team_scores_after,
        )
    )

    winner_team_id = next(
        (
            tid
            for tid, score in team_scores_after.items()
            if score >= game_state.settings.target_score
        ),
        None,
    )

    if winner_team_id is not None:
        game.status = "FINISHED"
        game.winner_team_id = winner_team_id
        game.finished_at = datetime.now(timezone.utc)
        game_state.current_deal = None
    else:
        players = (
            await session.scalars(select(Player).where(Player.game_id == game.id))
        ).all()
        seated = sorted(players, key=lambda p: p.seat)
        player_order = [p.id for p in seated]
        player_team = {p.id: p.team_id for p in seated}
        game_state.current_deal = start_new_deal(
            player_order, player_team, game_state.scores
        )
        game.current_deal_number += 1

    await session.commit()

    deal_result_message = {
        "type": "deal_result",
        "data": {
            "deal_number": deal_number,
            "scores_breakdown": score_breakdown,
            "team_scores_after": team_scores_after,
            "next_deal": winner_team_id is None,
        },
    }
    return deal_result_message, winner_team_id


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

        if not game_state.current_deal.deal_over:
            store.set_state(game.id, game_state)
            return GameIntentResult(
                game_state=game_state,
                deal_completed=False,
                deal_result_message=None,
                winner_team_id=None,
            )

        deal_result_message, winner_team_id = await _complete_deal(
            session, game, game_state
        )
        if game_state.current_deal is None:
            store.delete_state(game.id)
        else:
            store.set_state(game.id, game_state)

        return GameIntentResult(
            game_state=game_state,
            deal_completed=True,
            deal_result_message=deal_result_message,
            winner_team_id=winner_team_id,
        )
