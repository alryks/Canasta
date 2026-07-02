"""Turn state machine (see plan section 7): DRAW -> ACT -> DISCARD -> DEAL_END."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from app.engine.errors import IllegalActionError
from app.engine.models import Card

CONCEDE_PENALTY_POINTS = 1000


class TurnPhase(str, Enum):
    DRAW = "DRAW"
    ACT = "ACT"
    DISCARD = "DISCARD"
    DEAL_END = "DEAL_END"


@dataclass(frozen=True)
class TurnState:
    current_player_id: str
    phase: TurnPhase = TurnPhase.DRAW
    must_meld_after_pickup: bool = False
    melds_created_this_turn: int = 0
    pending_penalty: bool = False
    # ids of melds created this turn -- the engine rolls exactly these back
    # into the hand when an unopened team's discard falls below the threshold
    created_meld_ids: tuple[str, ...] = ()


def start_turn(player_id: str) -> TurnState:
    return TurnState(current_player_id=player_id, phase=TurnPhase.DRAW)


def draw_from_deck(turn_state: TurnState) -> TurnState:
    if turn_state.phase != TurnPhase.DRAW:
        raise IllegalActionError(f"cannot draw_deck during phase {turn_state.phase}")
    return replace(turn_state, phase=TurnPhase.ACT)


def draw_from_discard(turn_state: TurnState, top_of_discard: Card) -> TurnState:
    if turn_state.phase != TurnPhase.DRAW:
        raise IllegalActionError(f"cannot draw_discard during phase {turn_state.phase}")
    if top_of_discard.is_three:
        raise IllegalActionError("cannot take discard pile when a three is on top")
    return replace(turn_state, phase=TurnPhase.ACT, must_meld_after_pickup=True)


def record_meld_created(turn_state: TurnState, meld_id: str | None = None) -> TurnState:
    if turn_state.phase != TurnPhase.ACT:
        raise IllegalActionError(
            f"cannot create a meld during phase {turn_state.phase}"
        )
    created = (
        (*turn_state.created_meld_ids, meld_id)
        if meld_id is not None
        else turn_state.created_meld_ids
    )
    return replace(
        turn_state,
        melds_created_this_turn=turn_state.melds_created_this_turn + 1,
        created_meld_ids=created,
    )


def concede_penalty(turn_state: TurnState) -> TurnState:
    """FR-22.1/22.2: 'не могу выложить' — forces DISCARD to be allowed, -1000 penalty."""
    if turn_state.phase != TurnPhase.ACT:
        raise IllegalActionError(
            f"cannot concede_penalty during phase {turn_state.phase}"
        )
    return replace(turn_state, pending_penalty=True)


def can_discard(
    turn_state: TurnState, *, team_opened: bool, threshold_met: bool
) -> bool:
    if turn_state.phase != TurnPhase.ACT:
        return False
    if turn_state.pending_penalty:
        return True
    if not turn_state.must_meld_after_pickup:
        # rules.md section 6: after drawing from the deck melding is optional,
        # so a plain discard is always allowed regardless of opening status.
        return True
    # Took the whole discard pile (section 7): must have laid at least one new
    # meld this turn, and an unopened team must also cover its opening threshold.
    return turn_state.melds_created_this_turn > 0 and (team_opened or threshold_met)


def discard_incurring_penalty(
    turn_state: TurnState,
    *,
    team_opened: bool,
    threshold_met: bool,
) -> bool:
    """True when a discard should auto-apply the -1000 penalty (rules section 7).

    Only the took-the-pile-without-melding case remains here: below-threshold
    melds never reach a discard anymore -- the engine rolls them back to the
    hand and rejects the discard instead (rules.md section 10).
    """
    if turn_state.pending_penalty:
        return False
    if turn_state.must_meld_after_pickup and not can_discard(
        turn_state, team_opened=team_opened, threshold_met=threshold_met
    ):
        return True
    return False


def discard(
    turn_state: TurnState,
    *,
    team_opened: bool,
    threshold_met: bool,
    hand_empty_after: bool,
    team_has_closed_canasta: bool,
) -> TurnState:
    if turn_state.phase != TurnPhase.ACT:
        raise IllegalActionError(f"cannot discard during phase {turn_state.phase}")
    if not can_discard(
        turn_state, team_opened=team_opened, threshold_met=threshold_met
    ):
        raise IllegalActionError(
            "discard blocked: after taking the discard pile you must lay a new meld"
            " (and cover the opening threshold if your team is not opened)"
        )
    if hand_empty_after and team_has_closed_canasta:
        return replace(turn_state, phase=TurnPhase.DEAL_END, pending_penalty=False)
    return replace(turn_state, phase=TurnPhase.DISCARD, pending_penalty=False)


def go_out_clean(
    turn_state: TurnState, *, hand_empty: bool, team_has_closed_canasta: bool
) -> TurnState:
    """Clean exit (FR-19/13): last card goes into a meld, no discard needed."""
    if turn_state.phase != TurnPhase.ACT:
        raise IllegalActionError(f"cannot go_out during phase {turn_state.phase}")
    if not (hand_empty and team_has_closed_canasta):
        raise IllegalActionError(
            "cannot go out: hand not empty or team has no completed canasta"
        )
    return replace(turn_state, phase=TurnPhase.DEAL_END, pending_penalty=False)


def end_turn(turn_state: TurnState, next_player_id: str) -> TurnState:
    if turn_state.phase != TurnPhase.DISCARD:
        raise IllegalActionError(f"cannot end_turn during phase {turn_state.phase}")
    return start_turn(next_player_id)


def force_skip(turn_state: TurnState, next_player_id: str) -> TurnState:
    """FR-37: host's administrative skip after a disconnect timeout.

    Unlike `end_turn`, this is allowed from any in-progress phase (DRAW/ACT/
    DISCARD) since the stuck player may not have drawn or melded at all --
    it's an out-of-band override, not a normal player action.
    """
    if turn_state.phase == TurnPhase.DEAL_END:
        raise IllegalActionError("cannot skip turn: deal already over")
    return start_turn(next_player_id)
