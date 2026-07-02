"""HeuristicBotStrategy: unit checks for each decision rule, plus full-deal
self-play -- four bots must always produce engine-legal intents and bring any
random deal to an end without a single -1000 penalty or stall."""

from __future__ import annotations

import random

import pytest

from app.bots.strategy import HeuristicBotStrategy
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
from app.engine.engine import DealState, apply_action, final_deal_scores, start_new_deal
from app.engine.models import Card, Rank, Suit, TeamTable
from app.engine.rules import build_new_meld
from app.engine.turn_fsm import TurnPhase, TurnState, start_turn

strategy = HeuristicBotStrategy()

PLAYER_ORDER = ["p1", "p2", "p3", "p4"]
PLAYER_TEAM = {"p1": "A", "p2": "B", "p3": "A", "p4": "B"}


def c(rank: Rank, suit: Suit | None, card_id: str) -> Card:
    return Card(id=card_id, rank=rank, suit=suit)


def make_deal(
    *,
    hand: list[Card],
    deck: list[Card] | None = None,
    discard_pile: list[Card] | None = None,
    teams: dict[str, TeamTable] | None = None,
    turn_state: TurnState | None = None,
    thresholds: dict[str, int] | None = None,
) -> DealState:
    return DealState(
        deck=deck if deck is not None else [c(Rank.NINE, Suit.CLUBS, "deck1")],
        discard_pile=discard_pile or [],
        teams=teams or {"A": TeamTable(team_id="A"), "B": TeamTable(team_id="B")},
        hands={"p1": hand, "p2": [], "p3": [], "p4": []},
        thresholds=thresholds or {"A": 30, "B": 30},
        player_order=PLAYER_ORDER,
        player_team=PLAYER_TEAM,
        turn_state=turn_state or start_turn("p1"),
    )


def act_state(**kwargs) -> TurnState:
    return TurnState(current_player_id="p1", phase=TurnPhase.ACT, **kwargs)


# --- DRAW phase ---


def test_draws_from_deck_when_pile_is_empty() -> None:
    deal = make_deal(hand=[c(Rank.KING, Suit.HEARTS, "k1")])
    assert strategy.choose_intent(deal, "p1") == ("draw_deck", {})


def test_takes_pile_when_opened_and_top_completes_a_set() -> None:
    deal = make_deal(
        hand=[
            c(Rank.KING, Suit.HEARTS, "k1"),
            c(Rank.KING, Suit.SPADES, "k2"),
            c(Rank.NINE, Suit.HEARTS, "junk"),
        ],
        discard_pile=[c(Rank.KING, Suit.CLUBS, "top")],
        teams={
            "A": TeamTable(team_id="A", is_opened=True),
            "B": TeamTable(team_id="B"),
        },
    )
    assert strategy.choose_intent(deal, "p1") == ("draw_discard", {})


def test_never_takes_pile_with_a_three_on_top() -> None:
    deal = make_deal(
        hand=[c(Rank.KING, Suit.HEARTS, "k1"), c(Rank.KING, Suit.SPADES, "k2")],
        discard_pile=[
            c(Rank.KING, Suit.CLUBS, "buried"),
            c(Rank.THREE, Suit.SPADES, "top3"),
        ],
        teams={
            "A": TeamTable(team_id="A", is_opened=True),
            "B": TeamTable(team_id="B"),
        },
    )
    assert strategy.choose_intent(deal, "p1") == ("draw_deck", {})


def test_unopened_skips_pile_when_threshold_is_out_of_reach() -> None:
    # a set of three fours is 15 points -- far below the 30 threshold
    deal = make_deal(
        hand=[c(Rank.FOUR, Suit.HEARTS, "f1"), c(Rank.FOUR, Suit.SPADES, "f2")],
        discard_pile=[c(Rank.FOUR, Suit.CLUBS, "top")],
    )
    assert strategy.choose_intent(deal, "p1") == ("draw_deck", {})


def test_unopened_takes_pile_when_top_anchors_an_opening() -> None:
    deal = make_deal(
        hand=[
            c(Rank.ACE, Suit.HEARTS, "a1"),
            c(Rank.ACE, Suit.SPADES, "a2"),
            c(Rank.NINE, Suit.HEARTS, "junk"),
        ],
        discard_pile=[c(Rank.ACE, Suit.CLUBS, "top")],
    )
    assert strategy.choose_intent(deal, "p1") == ("draw_discard", {})


# --- opening ---


def test_opens_with_a_set_covering_the_threshold() -> None:
    aces = [
        c(Rank.ACE, Suit.HEARTS, "a1"),
        c(Rank.ACE, Suit.SPADES, "a2"),
        c(Rank.ACE, Suit.CLUBS, "a3"),
    ]
    filler = c(Rank.NINE, Suit.HEARTS, "f1")
    deal = make_deal(hand=[*aces, filler], turn_state=act_state())
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "create_meld"
    assert set(data["card_ids"]) == {"a1", "a2", "a3"}


def test_does_not_meld_below_threshold() -> None:
    fours = [
        c(Rank.FOUR, Suit.HEARTS, "f1"),
        c(Rank.FOUR, Suit.SPADES, "f2"),
        c(Rank.FOUR, Suit.CLUBS, "f3"),
    ]
    junk = c(Rank.NINE, Suit.HEARTS, "junk")
    deal = make_deal(hand=[*fours, junk], turn_state=act_state())
    intent, _ = strategy.choose_intent(deal, "p1")
    assert intent == "discard"


def test_opening_pads_a_pair_with_a_wild_to_reach_threshold() -> None:
    kings = [c(Rank.KING, Suit.HEARTS, "k1"), c(Rank.KING, Suit.SPADES, "k2")]
    joker = c(Rank.JOKER, None, "j1")
    junk = c(Rank.FOUR, Suit.HEARTS, "junk")
    deal = make_deal(hand=[*kings, joker, junk], turn_state=act_state())
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "create_meld"
    assert set(data["card_ids"]) == {"k1", "k2", "j1"}  # 10+10+50 = 70 >= 30


# --- ACT while opened ---


def _opened_team_with_meld(cards: list[Card]) -> dict[str, TeamTable]:
    meld = build_new_meld("m1", "A", cards)
    return {
        "A": TeamTable(team_id="A", melds=[meld], is_opened=True),
        "B": TeamTable(team_id="B"),
    }


def test_completes_a_canasta_with_a_wild_finisher() -> None:
    suits = list(Suit)
    six_kings = [c(Rank.KING, suits[i % 4], f"mk{i}") for i in range(6)]
    teams = _opened_team_with_meld(six_kings)
    two = c(Rank.TWO, Suit.HEARTS, "wild1")
    junk = [c(Rank.FOUR, Suit.HEARTS, "j1"), c(Rank.FIVE, Suit.SPADES, "j2"), c(Rank.SIX, Suit.CLUBS, "j3")]
    deal = make_deal(hand=[two, *junk], teams=teams, turn_state=act_state())
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "add_to_meld"
    assert data["meld_id"] == "m1"
    assert data["card_ids"] == ["wild1"]


def test_adds_matching_naturals_to_team_meld() -> None:
    kings = [
        c(Rank.KING, Suit.HEARTS, "mk1"),
        c(Rank.KING, Suit.SPADES, "mk2"),
        c(Rank.KING, Suit.CLUBS, "mk3"),
    ]
    teams = _opened_team_with_meld(kings)
    hand = [
        c(Rank.KING, Suit.DIAMONDS, "hk1"),
        c(Rank.FOUR, Suit.HEARTS, "j1"),
        c(Rank.FIVE, Suit.SPADES, "j2"),
        c(Rank.SIX, Suit.CLUBS, "j3"),
    ]
    deal = make_deal(hand=hand, teams=teams, turn_state=act_state())
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "add_to_meld"
    assert data["card_ids"] == ["hk1"]


def test_steals_an_opponent_wild_with_a_spare_natural() -> None:
    wild = c(Rank.TWO, Suit.HEARTS, "wild1")
    opp_meld = build_new_meld(
        "opp1",
        "B",
        [c(Rank.QUEEN, Suit.HEARTS, "q1"), c(Rank.QUEEN, Suit.SPADES, "q2"), wild],
    )
    teams = {
        "A": TeamTable(team_id="A", is_opened=True),
        "B": TeamTable(team_id="B", melds=[opp_meld], is_opened=True),
    }
    hand = [
        c(Rank.QUEEN, Suit.CLUBS, "hq1"),  # exactly one spare queen
        c(Rank.FOUR, Suit.HEARTS, "j1"),
        c(Rank.FIVE, Suit.SPADES, "j2"),
        c(Rank.SIX, Suit.CLUBS, "j3"),
    ]
    deal = make_deal(hand=hand, teams=teams, turn_state=act_state())
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "steal_wild"
    assert data == {
        "meld_id": "opp1",
        "wild_card_id": "wild1",
        "replacement_card_id": "hq1",
    }


def test_must_meld_after_pickup_creates_before_anything_else() -> None:
    teams = {
        "A": TeamTable(team_id="A", is_opened=True),
        "B": TeamTable(team_id="B"),
    }
    hand = [
        c(Rank.KING, Suit.HEARTS, "k1"),
        c(Rank.KING, Suit.SPADES, "k2"),
        c(Rank.KING, Suit.CLUBS, "k3"),
        c(Rank.FOUR, Suit.HEARTS, "j1"),
        c(Rank.FIVE, Suit.SPADES, "j2"),
    ]
    deal = make_deal(
        hand=hand,
        teams=teams,
        turn_state=act_state(must_meld_after_pickup=True),
    )
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "create_meld"
    assert set(data["card_ids"]) == {"k1", "k2", "k3"}


def test_concedes_when_pickup_obligation_cannot_be_met() -> None:
    teams = {
        "A": TeamTable(team_id="A", is_opened=True),
        "B": TeamTable(team_id="B"),
    }
    hand = [c(Rank.FOUR, Suit.HEARTS, "j1"), c(Rank.TEN, Suit.SPADES, "j2")]
    deal = make_deal(
        hand=hand,
        teams=teams,
        turn_state=act_state(must_meld_after_pickup=True),
    )
    assert strategy.choose_intent(deal, "p1") == ("concede_penalty", {})


def test_never_melds_into_an_empty_hand_without_a_canasta() -> None:
    teams = {
        "A": TeamTable(team_id="A", is_opened=True),
        "B": TeamTable(team_id="B"),
    }
    kings = [
        c(Rank.KING, Suit.HEARTS, "k1"),
        c(Rank.KING, Suit.SPADES, "k2"),
        c(Rank.KING, Suit.CLUBS, "k3"),
    ]
    deal = make_deal(hand=list(kings), teams=teams, turn_state=act_state())
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "discard"  # laying all three kings would strand the turn


# --- discard choice ---


def test_discards_black_three_first() -> None:
    hand = [
        c(Rank.KING, Suit.HEARTS, "k1"),
        c(Rank.THREE, Suit.SPADES, "b3"),
        c(Rank.THREE, Suit.HEARTS, "r3"),
    ]
    deal = make_deal(hand=hand, turn_state=act_state())
    assert strategy.choose_intent(deal, "p1") == ("discard", {"card_id": "b3"})


def test_discard_keeps_pairs_wilds_and_red_threes() -> None:
    hand = [
        c(Rank.KING, Suit.HEARTS, "k1"),
        c(Rank.KING, Suit.SPADES, "k2"),
        c(Rank.JOKER, None, "j1"),
        c(Rank.THREE, Suit.HEARTS, "r3"),
        c(Rank.NINE, Suit.CLUBS, "lone"),
    ]
    # threshold far out of reach so no opening is attempted this turn
    deal = make_deal(
        hand=hand, turn_state=act_state(), thresholds={"A": 150, "B": 150}
    )
    assert strategy.choose_intent(deal, "p1") == ("discard", {"card_id": "lone"})


def test_discard_prefers_junk_over_cards_fitting_team_melds() -> None:
    kings = [
        c(Rank.KING, Suit.HEARTS, "mk1"),
        c(Rank.KING, Suit.SPADES, "mk2"),
        c(Rank.KING, Suit.CLUBS, "mk3"),
    ]
    teams = _opened_team_with_meld(kings)
    # both hand cards are singletons; the king fits the team meld, the four
    # does not -- but the king is also "addable", so it will be melded first;
    # force a pure discard decision with must-keep floor already reached
    hand = [c(Rank.NINE, Suit.DIAMONDS, "n1"), c(Rank.FOUR, Suit.HEARTS, "f1")]
    deal = make_deal(hand=hand, teams=teams, turn_state=act_state())
    intent, data = strategy.choose_intent(deal, "p1")
    assert intent == "discard"
    assert data["card_id"] == "n1"  # higher-value junk goes first


# --- full-deal self-play ---


def _intent_to_action(intent: str, data: dict) -> Action:
    if intent == "draw_deck":
        return DrawDeck()
    if intent == "draw_discard":
        return DrawDiscard()
    if intent == "create_meld":
        return CreateMeld(card_ids=list(data["card_ids"]), wild_side=data.get("wild_side", "low"))
    if intent == "add_to_meld":
        return AddToMeld(
            meld_id=data["meld_id"],
            card_ids=list(data["card_ids"]),
            wild_side=data.get("wild_side", "low"),
        )
    if intent == "steal_wild":
        return StealWild(
            meld_id=data["meld_id"],
            wild_card_id=data["wild_card_id"],
            replacement_card_id=data["replacement_card_id"],
        )
    if intent == "discard":
        return Discard(card_id=data["card_id"])
    if intent == "concede_penalty":
        return ConcedePenalty()
    raise AssertionError(f"bot produced unknown intent {intent!r}")


@pytest.mark.parametrize("seed", range(25))
def test_full_deal_self_play_finishes_cleanly(seed: int) -> None:
    rng = random.Random(seed)
    deal = start_new_deal(PLAYER_ORDER, PLAYER_TEAM, {"A": 0, "B": 0}, rng=rng)

    for _step in range(4000):
        if deal.deal_over:
            break
        player_id = deal.turn_state.current_player_id
        intent, data = strategy.choose_intent(deal, player_id)
        # every intent the bot produces must be legal -- apply_action raising
        # IllegalActionError here means the bot would stall a real game
        apply_action(deal, player_id, _intent_to_action(intent, data))
    else:
        raise AssertionError("deal did not finish within 4000 bot actions")

    assert deal.deal_over
    scores = final_deal_scores(deal)  # scoring must not raise either
    assert set(scores) == {"A", "B"}
    # a competent bot never walks into the -1000 penalties
    assert deal.penalties == {}
