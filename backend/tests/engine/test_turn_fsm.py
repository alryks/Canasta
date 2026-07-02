import pytest

from app.engine.errors import IllegalActionError
from app.engine.models import Card, Rank, Suit
from app.engine.turn_fsm import (
    TurnPhase,
    can_discard,
    concede_penalty,
    discard,
    discard_incurring_penalty,
    draw_from_deck,
    draw_from_discard,
    end_turn,
    force_skip,
    go_out_clean,
    record_meld_created,
    start_turn,
)


def three_of(suit: Suit) -> Card:
    return Card(id="three", rank=Rank.THREE, suit=suit)


def natural(rank: Rank = Rank.SEVEN, suit: Suit = Suit.SPADES) -> Card:
    return Card(id="nat", rank=rank, suit=suit)


def test_start_turn_is_draw_phase() -> None:
    state = start_turn("p1")
    assert state.phase == TurnPhase.DRAW
    assert state.current_player_id == "p1"


def test_draw_deck_moves_to_act_without_pickup_requirement() -> None:
    state = start_turn("p1")
    state = draw_from_deck(state)
    assert state.phase == TurnPhase.ACT
    assert state.must_meld_after_pickup is False


def test_draw_discard_moves_to_act_and_requires_meld() -> None:
    state = start_turn("p1")
    state = draw_from_discard(state, natural())
    assert state.phase == TurnPhase.ACT
    assert state.must_meld_after_pickup is True


def test_draw_discard_blocked_when_three_on_top() -> None:
    state = start_turn("p1")
    with pytest.raises(IllegalActionError):
        draw_from_discard(state, three_of(Suit.HEARTS))


def test_cannot_draw_twice_in_same_turn() -> None:
    state = draw_from_deck(start_turn("p1"))
    with pytest.raises(IllegalActionError):
        draw_from_deck(state)


def test_discard_blocked_without_meld_after_discard_pickup() -> None:
    state = draw_from_discard(start_turn("p1"), natural())
    assert not can_discard(state, team_opened=True, threshold_met=True)
    with pytest.raises(IllegalActionError):
        discard(
            state,
            team_opened=True,
            threshold_met=True,
            hand_empty_after=False,
            team_has_closed_canasta=False,
        )


def test_discard_allowed_after_required_meld_created() -> None:
    state = draw_from_discard(start_turn("p1"), natural())
    state = record_meld_created(state)
    assert can_discard(state, team_opened=True, threshold_met=True)
    state = discard(
        state,
        team_opened=True,
        threshold_met=True,
        hand_empty_after=False,
        team_has_closed_canasta=False,
    )
    assert state.phase == TurnPhase.DISCARD


def test_discard_free_after_deck_draw_even_if_team_not_opened() -> None:
    # rules.md section 6: after drawing from the deck melding is optional.
    state = draw_from_deck(start_turn("p1"))
    assert can_discard(state, team_opened=False, threshold_met=False)
    state = discard(
        state,
        team_opened=False,
        threshold_met=False,
        hand_empty_after=False,
        team_has_closed_canasta=False,
    )
    assert state.phase == TurnPhase.DISCARD


def test_discard_blocked_after_pickup_when_threshold_not_met() -> None:
    # rules.md section 7: after taking the discard pile an unopened team must
    # cover the opening threshold with this turn's melds.
    state = draw_from_discard(start_turn("p1"), natural())
    state = record_meld_created(state)
    assert not can_discard(state, team_opened=False, threshold_met=False)
    with pytest.raises(IllegalActionError):
        discard(
            state,
            team_opened=False,
            threshold_met=False,
            hand_empty_after=False,
            team_has_closed_canasta=False,
        )


def test_discard_allowed_when_team_already_opened() -> None:
    state = draw_from_deck(start_turn("p1"))
    state = discard(
        state,
        team_opened=True,
        threshold_met=False,
        hand_empty_after=False,
        team_has_closed_canasta=False,
    )
    assert state.phase == TurnPhase.DISCARD


def test_discard_allowed_when_threshold_met_this_turn() -> None:
    state = draw_from_deck(start_turn("p1"))
    state = discard(
        state,
        team_opened=False,
        threshold_met=True,
        hand_empty_after=False,
        team_has_closed_canasta=False,
    )
    assert state.phase == TurnPhase.DISCARD


def test_concede_penalty_edge_case_forces_discard_through() -> None:
    """FR-22.1/22.2: player physically cannot meet the requirement."""
    state = draw_from_discard(start_turn("p1"), natural())
    # stuck: must_meld_after_pickup not satisfied, cannot discard normally
    assert not can_discard(state, team_opened=False, threshold_met=False)
    assert discard_incurring_penalty(state, team_opened=False, threshold_met=False)

    state = concede_penalty(state)
    assert state.pending_penalty is True
    assert can_discard(state, team_opened=False, threshold_met=False)

    state = discard(
        state,
        team_opened=False,
        threshold_met=False,
        hand_empty_after=False,
        team_has_closed_canasta=False,
    )
    assert state.phase == TurnPhase.DISCARD
    assert state.pending_penalty is False


def test_concede_penalty_only_valid_during_act() -> None:
    state = start_turn("p1")
    with pytest.raises(IllegalActionError):
        concede_penalty(state)


def test_dirty_exit_via_discard_transitions_to_deal_end() -> None:
    state = draw_from_deck(start_turn("p1"))
    state = discard(
        state,
        team_opened=True,
        threshold_met=True,
        hand_empty_after=True,
        team_has_closed_canasta=True,
    )
    assert state.phase == TurnPhase.DEAL_END


def test_clean_exit_go_out_bypasses_discard() -> None:
    state = draw_from_deck(start_turn("p1"))
    state = go_out_clean(state, hand_empty=True, team_has_closed_canasta=True)
    assert state.phase == TurnPhase.DEAL_END


def test_clean_exit_requires_closed_canasta() -> None:
    state = draw_from_deck(start_turn("p1"))
    with pytest.raises(IllegalActionError):
        go_out_clean(state, hand_empty=True, team_has_closed_canasta=False)


def test_end_turn_requires_discard_phase() -> None:
    state = draw_from_deck(start_turn("p1"))
    with pytest.raises(IllegalActionError):
        end_turn(state, "p2")


def test_end_turn_starts_fresh_draw_for_next_player() -> None:
    state = draw_from_deck(start_turn("p1"))
    state = discard(
        state,
        team_opened=True,
        threshold_met=True,
        hand_empty_after=False,
        team_has_closed_canasta=False,
    )
    state = end_turn(state, "p2")
    assert state.current_player_id == "p2"
    assert state.phase == TurnPhase.DRAW


@pytest.mark.parametrize("state", [start_turn("p1"), draw_from_deck(start_turn("p1"))])
def test_force_skip_allowed_from_draw_or_act_phase(state) -> None:
    result = force_skip(state, "p2")
    assert result.current_player_id == "p2"
    assert result.phase == TurnPhase.DRAW


def test_force_skip_rejected_once_deal_already_ended() -> None:
    state = draw_from_deck(start_turn("p1"))
    state = discard(
        state,
        team_opened=True,
        threshold_met=True,
        hand_empty_after=True,
        team_has_closed_canasta=True,
    )
    assert state.phase == TurnPhase.DEAL_END
    with pytest.raises(IllegalActionError):
        force_skip(state, "p2")
    assert state.must_meld_after_pickup is False
    assert state.melds_created_this_turn == 0
    assert state.pending_penalty is False
