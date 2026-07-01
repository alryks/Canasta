from collections import Counter

from app.engine.models import Rank, Suit, generate_deck


def test_deck_has_108_cards() -> None:
    deck = generate_deck()
    assert len(deck) == 108


def test_deck_ids_are_unique() -> None:
    deck = generate_deck()
    ids = {card.id for card in deck}
    assert len(ids) == 108


def test_deck_rank_composition() -> None:
    deck = generate_deck()
    rank_counts = Counter(card.rank for card in deck)

    for rank in Rank:
        if rank == Rank.JOKER:
            assert rank_counts[rank] == 4
        else:
            assert rank_counts[rank] == 8, f"{rank} expected 8, got {rank_counts[rank]}"


def test_deck_suit_composition_for_non_jokers() -> None:
    deck = generate_deck()
    non_jokers = [c for c in deck if c.rank != Rank.JOKER]
    suit_counts = Counter(c.suit for c in non_jokers)
    for suit in Suit:
        assert suit_counts[suit] == 26  # 13 ranks x 2 decks


def test_wild_count_is_12() -> None:
    deck = generate_deck()
    wild_count = sum(1 for c in deck if c.is_wild)
    assert wild_count == 12  # 8 twos + 4 jokers


def test_jokers_have_no_suit() -> None:
    deck = generate_deck()
    for card in deck:
        if card.rank == Rank.JOKER:
            assert card.suit is None
        else:
            assert card.suit is not None
