import pytest

from app.engine.errors import IllegalActionError
from app.engine.models import Card, MeldKind, Rank, Suit
from app.engine.rules import add_to_meld, build_new_meld, steal_wild


def nat(rank: Rank, suit: Suit, tag: str = "") -> Card:
    return Card(id=f"{rank}{suit}{tag}", rank=rank, suit=suit)


def two(suit: Suit = Suit.HEARTS, tag: str = "") -> Card:
    return Card(id=f"2{suit}{tag}", rank=Rank.TWO, suit=suit)


def joker(tag: str = "") -> Card:
    return Card(id=f"J{tag}", rank=Rank.JOKER, suit=None)


# --- build_new_meld: SET ---


def test_build_set_from_naturals() -> None:
    cards = [nat(Rank.SEVEN, Suit.SPADES), nat(Rank.SEVEN, Suit.HEARTS), nat(Rank.SEVEN, Suit.CLUBS)]
    meld = build_new_meld("m1", "teamA", MeldKind.SET, cards)
    assert meld.kind == MeldKind.SET
    assert meld.rank_or_suit_anchor == Rank.SEVEN.value
    assert meld.size == 3


def test_set_rejects_mixed_ranks() -> None:
    cards = [nat(Rank.SEVEN, Suit.SPADES), nat(Rank.EIGHT, Suit.HEARTS), nat(Rank.SEVEN, Suit.CLUBS)]
    with pytest.raises(IllegalActionError):
        build_new_meld("m1", "teamA", MeldKind.SET, cards)


def test_set_rejects_too_many_wilds() -> None:
    cards = [nat(Rank.SEVEN, Suit.SPADES), two(tag="a"), two(tag="b")]
    with pytest.raises(IllegalActionError):
        build_new_meld("m1", "teamA", MeldKind.SET, cards)


def test_meld_requires_at_least_3_cards() -> None:
    cards = [nat(Rank.SEVEN, Suit.SPADES), nat(Rank.SEVEN, Suit.HEARTS)]
    with pytest.raises(IllegalActionError):
        build_new_meld("m1", "teamA", MeldKind.SET, cards)


def test_two_cannot_anchor_a_natural_set() -> None:
    cards = [nat(Rank.TWO, Suit.SPADES, "n1"), nat(Rank.TWO, Suit.HEARTS, "n2"), nat(Rank.TWO, Suit.CLUBS, "n3")]
    # twos are always wild -- there is no such thing as a "natural" two
    assert cards[0].is_wild


# --- build_new_meld: SEQUENCE ---


def test_build_sequence_from_naturals() -> None:
    cards = [nat(Rank.FOUR, Suit.SPADES), nat(Rank.FIVE, Suit.SPADES), nat(Rank.SIX, Suit.SPADES)]
    meld = build_new_meld("m2", "teamA", MeldKind.SEQUENCE, cards)
    assert meld.rank_or_suit_anchor == f"{Suit.SPADES.value}:{Rank.FOUR.value}"
    assert [c.rank for c in meld.slots] == [Rank.FOUR, Rank.FIVE, Rank.SIX]


def test_sequence_wild_fills_gap() -> None:
    cards = [nat(Rank.FOUR, Suit.SPADES), two(Suit.SPADES), nat(Rank.SIX, Suit.SPADES)]
    meld = build_new_meld("m3", "teamA", MeldKind.SEQUENCE, cards)
    assert meld.slots[1].is_wild
    assert meld.slots[0].rank == Rank.FOUR
    assert meld.slots[2].rank == Rank.SIX


def test_sequence_rejects_mixed_suit() -> None:
    cards = [nat(Rank.FOUR, Suit.SPADES), nat(Rank.FIVE, Suit.HEARTS), nat(Rank.SIX, Suit.SPADES)]
    with pytest.raises(IllegalActionError):
        build_new_meld("m4", "teamA", MeldKind.SEQUENCE, cards)


def test_sequence_rejects_gap_too_large_to_bridge() -> None:
    # FOUR..ACE spans the entire 11-rank window; only 2 wilds can't cover it.
    cards = [nat(Rank.FOUR, Suit.SPADES), nat(Rank.ACE, Suit.SPADES), two(Suit.SPADES), two(Suit.HEARTS, "b")]
    with pytest.raises(IllegalActionError):
        build_new_meld("m5", "teamA", MeldKind.SEQUENCE, cards)


# --- build_new_meld: WILD_CANASTA ---


def test_wild_canasta_requires_only_wild_cards() -> None:
    cards = [two(tag="a"), two(tag="b"), nat(Rank.SEVEN, Suit.SPADES)]
    with pytest.raises(IllegalActionError):
        build_new_meld("m6", "teamA", MeldKind.WILD_CANASTA, cards)


def test_wild_canasta_of_twos_and_jokers() -> None:
    cards = [two(tag="a"), two(tag="b"), joker(tag="c")]
    meld = build_new_meld("m7", "teamA", MeldKind.WILD_CANASTA, cards)
    assert meld.kind == MeldKind.WILD_CANASTA
    assert meld.size == 3


# --- add_to_meld ---


def test_add_to_meld_blocks_other_team() -> None:
    meld = build_new_meld(
        "m8", "teamA", MeldKind.SET, [nat(Rank.SEVEN, Suit.SPADES, "1"), nat(Rank.SEVEN, Suit.HEARTS, "2"), nat(Rank.SEVEN, Suit.CLUBS, "3")]
    )
    with pytest.raises(IllegalActionError):
        add_to_meld(meld, "teamB", [nat(Rank.SEVEN, Suit.DIAMONDS, "4")])


def test_add_to_meld_blocks_closed_canasta() -> None:
    cards = [nat(Rank.SEVEN, Suit.SPADES, str(i)) for i in range(7)]
    meld = build_new_meld("m9", "teamA", MeldKind.SET, cards)
    assert meld.is_closed
    with pytest.raises(IllegalActionError):
        add_to_meld(meld, "teamA", [nat(Rank.SEVEN, Suit.HEARTS, "extra")])


def test_add_to_meld_extends_set() -> None:
    cards = [nat(Rank.SEVEN, Suit.SPADES, "1"), nat(Rank.SEVEN, Suit.HEARTS, "2"), nat(Rank.SEVEN, Suit.CLUBS, "3")]
    meld = build_new_meld("m10", "teamA", MeldKind.SET, cards)
    updated = add_to_meld(meld, "teamA", [nat(Rank.SEVEN, Suit.DIAMONDS, "4")])
    assert updated.size == 4


def test_add_to_meld_extends_sequence_upward() -> None:
    cards = [nat(Rank.FOUR, Suit.SPADES), nat(Rank.FIVE, Suit.SPADES), nat(Rank.SIX, Suit.SPADES)]
    meld = build_new_meld("m11", "teamA", MeldKind.SEQUENCE, cards)
    updated = add_to_meld(meld, "teamA", [nat(Rank.SEVEN, Suit.SPADES)])
    assert [c.rank for c in updated.slots] == [Rank.FOUR, Rank.FIVE, Rank.SIX, Rank.SEVEN]


def test_add_to_meld_rejects_wrong_suit_for_sequence() -> None:
    cards = [nat(Rank.FOUR, Suit.SPADES), nat(Rank.FIVE, Suit.SPADES), nat(Rank.SIX, Suit.SPADES)]
    meld = build_new_meld("m12", "teamA", MeldKind.SEQUENCE, cards)
    with pytest.raises(IllegalActionError):
        add_to_meld(meld, "teamA", [nat(Rank.SEVEN, Suit.HEARTS)])


# --- steal_wild ---


def _dirty_set_with_wild() -> tuple:
    wild = two(Suit.HEARTS, "steal")
    cards = [nat(Rank.SEVEN, Suit.SPADES, "1"), nat(Rank.SEVEN, Suit.CLUBS, "2"), wild]
    meld = build_new_meld("m13", "teamB", MeldKind.SET, cards)
    return meld, wild


def test_steal_wild_from_set_succeeds() -> None:
    meld, wild = _dirty_set_with_wild()
    replacement = nat(Rank.SEVEN, Suit.DIAMONDS, "repl")
    updated, stolen = steal_wild(
        meld, stealing_team_id="teamA", wild_card_id=wild.id, replacement_card=replacement
    )
    assert stolen.id == wild.id
    assert replacement in updated.slots
    assert updated.size == 3


def test_steal_wild_blocks_own_team() -> None:
    meld, wild = _dirty_set_with_wild()
    replacement = nat(Rank.SEVEN, Suit.DIAMONDS, "repl")
    with pytest.raises(IllegalActionError):
        steal_wild(
            meld, stealing_team_id="teamB", wild_card_id=wild.id, replacement_card=replacement
        )


def test_steal_wild_blocks_wrong_replacement_rank() -> None:
    meld, wild = _dirty_set_with_wild()
    wrong_replacement = nat(Rank.EIGHT, Suit.DIAMONDS, "wrong")
    with pytest.raises(IllegalActionError):
        steal_wild(
            meld,
            stealing_team_id="teamA",
            wild_card_id=wild.id,
            replacement_card=wrong_replacement,
        )


def test_steal_wild_blocks_wild_canasta() -> None:
    cards = [two(tag="a"), two(tag="b"), joker(tag="c")]
    meld = build_new_meld("m14", "teamB", MeldKind.WILD_CANASTA, cards)
    with pytest.raises(IllegalActionError):
        steal_wild(
            meld,
            stealing_team_id="teamA",
            wild_card_id=cards[0].id,
            replacement_card=nat(Rank.SEVEN, Suit.DIAMONDS),
        )


def test_steal_wild_from_sequence_requires_exact_position() -> None:
    wild = two(Suit.SPADES, "seq")
    cards = [nat(Rank.FOUR, Suit.SPADES), wild, nat(Rank.SIX, Suit.SPADES)]
    meld = build_new_meld("m15", "teamB", MeldKind.SEQUENCE, cards)

    with pytest.raises(IllegalActionError):
        steal_wild(
            meld,
            stealing_team_id="teamA",
            wild_card_id=wild.id,
            replacement_card=nat(Rank.SIX, Suit.SPADES, "wrongrank"),
        )

    updated, stolen = steal_wild(
        meld,
        stealing_team_id="teamA",
        wild_card_id=wild.id,
        replacement_card=nat(Rank.FIVE, Suit.SPADES, "correct"),
    )
    assert stolen.id == wild.id
    assert updated.slots[1].rank == Rank.FIVE
