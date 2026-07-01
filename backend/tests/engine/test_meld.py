from app.engine.models import CanastaType, Card, Meld, MeldKind, Rank, Suit


def natural(rank: Rank, suit: Suit = Suit.SPADES, idx: int = 0) -> Card:
    return Card(id=f"n{rank}{suit}{idx}", rank=rank, suit=suit)


def wild_two(suit: Suit = Suit.HEARTS, idx: int = 0) -> Card:
    return Card(id=f"w2{suit}{idx}", rank=Rank.TWO, suit=suit)


def wild_joker(idx: int = 0) -> Card:
    return Card(id=f"wj{idx}", rank=Rank.JOKER, suit=None)


def test_clean_canasta_bonus() -> None:
    slots = [natural(Rank.SEVEN, idx=i) for i in range(7)]
    meld = Meld(
        id="m1", team_id="t1", kind=MeldKind.SET, rank_or_suit_anchor="7", slots=slots
    )
    assert meld.is_closed
    assert meld.canasta_type == CanastaType.CLEAN
    assert meld.canasta_bonus == 500
    assert meld.point_value == 7 * 5


def test_dirty_canasta_bonus() -> None:
    slots = [natural(Rank.SEVEN, idx=i) for i in range(6)] + [wild_two()]
    meld = Meld(
        id="m2", team_id="t1", kind=MeldKind.SET, rank_or_suit_anchor="7", slots=slots
    )
    assert meld.is_closed
    assert meld.canasta_type == CanastaType.DIRTY
    assert meld.canasta_bonus == 200


def test_wild_canasta_bonus() -> None:
    slots = [wild_two(idx=i) for i in range(6)] + [wild_joker()]
    meld = Meld(
        id="m3",
        team_id="t1",
        kind=MeldKind.WILD_CANASTA,
        rank_or_suit_anchor="",
        slots=slots,
    )
    assert meld.is_closed
    assert meld.canasta_type == CanastaType.WILD
    assert meld.canasta_bonus == 1000
    assert meld.point_value == 6 * 10 + 50


def test_unclosed_meld_has_no_canasta_type() -> None:
    slots = [natural(Rank.SEVEN, idx=i) for i in range(3)]
    meld = Meld(
        id="m4", team_id="t1", kind=MeldKind.SET, rank_or_suit_anchor="7", slots=slots
    )
    assert not meld.is_closed
    assert meld.canasta_type is None
    assert meld.canasta_bonus == 0


def test_wild_limit_respected_when_wilds_not_exceeding_naturals() -> None:
    slots = [natural(Rank.SEVEN, idx=i) for i in range(4)] + [
        wild_two(idx=0),
        wild_two(idx=1),
    ]
    meld = Meld(
        id="m5", team_id="t1", kind=MeldKind.SET, rank_or_suit_anchor="7", slots=slots
    )
    assert meld.respects_wild_limit


def test_wild_limit_violated_when_wilds_exceed_naturals() -> None:
    slots = [natural(Rank.SEVEN, idx=0)] + [wild_two(idx=i) for i in range(2)]
    meld = Meld(
        id="m6", team_id="t1", kind=MeldKind.SET, rank_or_suit_anchor="7", slots=slots
    )
    assert not meld.respects_wild_limit


def test_wild_canasta_exempt_from_wild_limit() -> None:
    slots = [wild_two(idx=i) for i in range(7)]
    meld = Meld(
        id="m7",
        team_id="t1",
        kind=MeldKind.WILD_CANASTA,
        rank_or_suit_anchor="",
        slots=slots,
    )
    assert meld.respects_wild_limit
