"""Bot decision-making (plan follow-up: fill empty lobby seats with bots so a
game can be tested/played without needing 4 humans).

`BotStrategy` is the one seam a smarter bot plugs into later -- a strategy
only has to answer "what's my next WS intent", it never touches the engine,
Redis, or broadcasting directly. `app/ws/bot_runner.py` drives it against the
exact same `apply_game_intent` pipeline real WS messages go through, so a
bot is indistinguishable from a slow human from the engine's point of view.
"""

from __future__ import annotations

from typing import Protocol

from app.engine.engine import DealState
from app.engine.turn_fsm import TurnPhase, can_discard


class BotStrategy(Protocol):
    def choose_intent(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        """Return the next (intent, data) to send on this bot's turn -- called
        again after every resulting game_state, same as a real client reacting
        to each snapshot, until the turn passes to someone else."""
        ...


class SimpleBotStrategy:
    """Draws from the deck and immediately discards the first card in hand;
    concedes the standard -1000 penalty (FR-22.1/22.2, same path as the
    human "не могу выложить" button) instead of attempting to build melds
    whenever a plain discard would otherwise be blocked. Never takes the
    discard pile (avoids the must-meld-after-pickup obligation entirely) and
    never melds -- a future e.g. HeuristicBotStrategy that actually builds
    melds registers in BOT_STRATEGIES the same way.
    """

    def choose_intent(self, deal: DealState, player_id: str) -> tuple[str, dict]:
        turn = deal.turn_state

        if turn.phase == TurnPhase.DRAW:
            return "draw_deck", {}

        if turn.phase == TurnPhase.ACT:
            team_id = deal.player_team[player_id]
            team = deal.teams[team_id]
            threshold_met = team.turn_accumulator >= deal.thresholds[team_id]
            if can_discard(turn, team_opened=team.is_opened, threshold_met=threshold_met):
                hand = deal.hands[player_id]
                return "discard", {"card_id": hand[0].id}
            return "concede_penalty", {}

        raise RuntimeError(f"SimpleBotStrategy has no move for phase {turn.phase!r}")


BOT_STRATEGIES: dict[str, BotStrategy] = {"simple": SimpleBotStrategy()}
DEFAULT_BOT_STRATEGY = "simple"
