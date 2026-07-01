from app.engine.models import Card, Meld, MeldKind, Rank, Suit, TeamTable
from app.engine.scoring import ExitType, score_deal, score_team_deal


def nat(rank: Rank, suit: Suit, tag: str = "") -> Card:
    return Card(id=f"{rank}{suit}{tag}", rank=rank, suit=suit)


def two(suit: Suit = Suit.HEARTS, tag: str = "") -> Card:
    return Card(id=f"2{suit}{tag}", rank=Rank.TWO, suit=suit)


def joker(tag: str = "") -> Card:
    return Card(id=f"J{tag}", rank=Rank.JOKER, suit=None)


def red_three(tag: str = "") -> Card:
    return Card(id=f"3r{tag}", rank=Rank.THREE, suit=Suit.HEARTS)


def black_three(tag: str = "") -> Card:
    return Card(id=f"3b{tag}", rank=Rank.THREE, suit=Suit.SPADES)


def test_scenario_clean_canasta_not_exiting() -> None:
    # 7 natural sevens: 7*5=35 base + 500 clean bonus.
    slots = [nat(Rank.SEVEN, Suit.SPADES, str(i)) for i in range(7)]
    meld = Meld(
        id="m1", team_id="A", kind=MeldKind.SET, rank_or_suit_anchor="7", slots=slots
    )
    team_table = TeamTable(team_id="A", melds=[meld], is_opened=True)

    hand = [red_three(), black_three(), nat(Rank.EIGHT, Suit.CLUBS)]
    result = score_team_deal(team_table, hand, went_out=False)

    assert result.table_points == 35
    assert result.canasta_bonus == 500
    assert result.hand_penalty == -5
    assert result.three_bonus == 0  # +100 red, -100 black cancel out
    assert result.exit_bonus == 0
    assert result.total == 35 + 500 - 5


def test_scenario_no_canasta_table_cards_count_negative() -> None:
    # Partial meld of 3 eights (15 points), no canasta -> counts as minus.
    slots = [nat(Rank.EIGHT, Suit.SPADES, str(i)) for i in range(3)]
    meld = Meld(
        id="m2", team_id="B", kind=MeldKind.SET, rank_or_suit_anchor="8", slots=slots
    )
    team_table = TeamTable(team_id="B", melds=[meld], is_opened=True)

    hand = [nat(Rank.TEN, Suit.SPADES), nat(Rank.JACK, Suit.HEARTS)]  # 10+10=20
    result = score_team_deal(team_table, hand, went_out=False)

    assert result.table_points == -15
    assert result.canasta_bonus == 0
    assert result.hand_penalty == -20
    assert result.total == -15 - 20


def test_scenario_clean_exit_with_dirty_canasta() -> None:
    # 5 natural sevens + 2 wild twos: dirty canasta, 5*5+2*10=45 base, +200 bonus.
    slots = [nat(Rank.SEVEN, Suit.SPADES, str(i)) for i in range(5)] + [
        two(Suit.HEARTS, "a"),
        two(Suit.DIAMONDS, "b"),
    ]
    meld = Meld(
        id="m3", team_id="C", kind=MeldKind.SET, rank_or_suit_anchor="7", slots=slots
    )
    team_table = TeamTable(team_id="C", melds=[meld], is_opened=True)

    result = score_team_deal(team_table, [], went_out=True, exit_type=ExitType.CLEAN)

    assert result.table_points == 45
    assert result.canasta_bonus == 200
    assert result.hand_penalty == 0
    assert result.exit_bonus == 400
    assert result.total == 45 + 200 + 400


def test_scenario_dirty_exit_with_wild_canasta() -> None:
    # 5 twos + 2 jokers: 5*10+2*50=150 base, wild canasta bonus 1000.
    slots = [two(Suit.HEARTS, str(i)) for i in range(5)] + [joker("a"), joker("b")]
    meld = Meld(
        id="m4",
        team_id="D",
        kind=MeldKind.WILD_CANASTA,
        rank_or_suit_anchor="",
        slots=slots,
    )
    team_table = TeamTable(team_id="D", melds=[meld], is_opened=True)

    result = score_team_deal(team_table, [], went_out=True, exit_type=ExitType.DIRTY)

    assert result.table_points == 150
    assert result.canasta_bonus == 1000
    assert result.exit_bonus == 200
    assert result.total == 150 + 1000 + 200


def test_score_deal_only_credits_exit_bonus_to_the_exiting_team() -> None:
    meld_a = Meld(
        id="ma",
        team_id="A",
        kind=MeldKind.SET,
        rank_or_suit_anchor="7",
        slots=[nat(Rank.SEVEN, Suit.SPADES, str(i)) for i in range(7)],
    )
    meld_b = Meld(
        id="mb",
        team_id="B",
        kind=MeldKind.SET,
        rank_or_suit_anchor="8",
        slots=[nat(Rank.EIGHT, Suit.SPADES, str(i)) for i in range(7)],
    )
    teams = {
        "A": TeamTable(team_id="A", melds=[meld_a], is_opened=True),
        "B": TeamTable(team_id="B", melds=[meld_b], is_opened=True),
    }
    hands = {"A": [], "B": [nat(Rank.NINE, Suit.CLUBS)]}

    results = score_deal(teams, hands, went_out_team_id="A", exit_type=ExitType.CLEAN)

    assert results["A"].exit_bonus == 400
    assert results["B"].exit_bonus == 0
