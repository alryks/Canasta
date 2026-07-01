"""Validation for create_meld, add_to_meld, steal_wild (plan section 3.3/3.5, rules.md 8/9/12)."""

from __future__ import annotations

from app.engine.errors import IllegalActionError
from app.engine.models import (
    CANASTA_SIZE,
    MELDABLE_RANKS,
    Card,
    Meld,
    MeldKind,
    Rank,
    Suit,
)


def _split_wild_natural(cards: list[Card]) -> tuple[list[Card], list[Card]]:
    naturals = [c for c in cards if not c.is_wild]
    wilds = [c for c in cards if c.is_wild]
    return naturals, wilds


def _build_sequence_slots(cards: list[Card]) -> tuple[int, list[Card]]:
    """Fit `cards` (single suit, distinct natural ranks + wild fillers) into a
    contiguous window of MELDABLE_RANKS. Returns (anchor_start, ordered slots)."""
    naturals, wilds = _split_wild_natural(cards)
    if not naturals:
        raise IllegalActionError("a sequence needs at least one natural card")

    suit = naturals[0].suit
    if any(c.suit != suit for c in naturals):
        raise IllegalActionError(
            "all natural cards in a sequence must share the same suit"
        )

    indices = sorted(MELDABLE_RANKS.index(c.rank) for c in naturals)
    if len(set(indices)) != len(indices):
        raise IllegalActionError("a sequence cannot repeat the same rank twice")

    low, high = indices[0], indices[-1]
    window_needed = high - low + 1
    extra = len(cards) - window_needed
    if extra < 0:
        raise IllegalActionError(
            "not enough wild cards to bridge the gaps in this sequence"
        )
    low_room = low
    high_room = len(MELDABLE_RANKS) - 1 - high
    if extra > low_room + high_room:
        raise IllegalActionError("sequence would have to run past 4 or past Ace")
    anchor_start = low - min(extra, low_room)

    slots: list[Card | None] = [None] * len(cards)
    for card in naturals:
        pos = MELDABLE_RANKS.index(card.rank) - anchor_start
        slots[pos] = card
    remaining_wilds = list(wilds)
    for pos in range(len(cards)):
        if slots[pos] is None:
            slots[pos] = remaining_wilds.pop()

    return anchor_start, [c for c in slots if c is not None]


def build_new_meld(
    meld_id: str, team_id: str, kind: MeldKind, cards: list[Card]
) -> Meld:
    if len(cards) < 3:
        raise IllegalActionError("a new meld needs at least 3 cards")

    if kind == MeldKind.WILD_CANASTA:
        if not all(c.is_wild for c in cards):
            raise IllegalActionError("a wild canasta must be made only of 2s/jokers")
        return Meld(
            id=meld_id,
            team_id=team_id,
            kind=kind,
            rank_or_suit_anchor="",
            slots=list(cards),
        )

    naturals, wilds = _split_wild_natural(cards)
    if not naturals:
        raise IllegalActionError(f"{kind.value} meld needs at least one natural card")
    if len(wilds) > len(naturals):
        raise IllegalActionError(
            "wild cards cannot outnumber natural cards in this meld"
        )

    if kind == MeldKind.SET:
        rank = naturals[0].rank
        if rank not in MELDABLE_RANKS:
            raise IllegalActionError(f"rank {rank} cannot form a set")
        if any(c.rank != rank for c in naturals):
            raise IllegalActionError(
                "all natural cards in a set must share the same rank"
            )
        return Meld(
            id=meld_id,
            team_id=team_id,
            kind=kind,
            rank_or_suit_anchor=rank.value,
            slots=list(cards),
        )

    if kind == MeldKind.SEQUENCE:
        suit = naturals[0].suit
        anchor_start, slots = _build_sequence_slots(cards)
        anchor = f"{suit.value}:{MELDABLE_RANKS[anchor_start].value}"
        return Meld(
            id=meld_id,
            team_id=team_id,
            kind=kind,
            rank_or_suit_anchor=anchor,
            slots=slots,
        )

    raise IllegalActionError(f"unknown meld kind {kind}")


def _sequence_anchor(meld: Meld) -> tuple[Suit, int]:
    suit_value, start_rank_value = meld.rank_or_suit_anchor.split(":")
    return Suit(suit_value), MELDABLE_RANKS.index(Rank(start_rank_value))


def add_to_meld(meld: Meld, team_id: str, cards: list[Card]) -> Meld:
    if meld.team_id != team_id:
        raise IllegalActionError("cannot add cards to another team's meld")
    if meld.is_closed:
        raise IllegalActionError("cannot add cards to a completed canasta (7 cards)")
    if not cards:
        raise IllegalActionError("no cards to add")

    new_size = meld.size + len(cards)
    if new_size > CANASTA_SIZE:
        raise IllegalActionError("a canasta cannot exceed 7 cards")

    if meld.kind == MeldKind.WILD_CANASTA:
        if not all(c.is_wild for c in cards):
            raise IllegalActionError("a wild canasta can only take wild cards")
        return Meld(
            id=meld.id,
            team_id=meld.team_id,
            kind=meld.kind,
            rank_or_suit_anchor=meld.rank_or_suit_anchor,
            slots=[*meld.slots, *cards],
        )

    naturals, _wilds = _split_wild_natural(cards)

    if meld.kind == MeldKind.SET:
        rank = Rank(meld.rank_or_suit_anchor)
        if any(c.rank != rank for c in naturals):
            raise IllegalActionError(f"only rank {rank.value} cards fit into this set")
        new_slots = [*meld.slots, *cards]
        new_wild = sum(1 for c in new_slots if c.is_wild)
        if new_wild > (len(new_slots) - new_wild):
            raise IllegalActionError(
                "wild cards cannot outnumber natural cards in this meld"
            )
        return Meld(
            id=meld.id,
            team_id=meld.team_id,
            kind=meld.kind,
            rank_or_suit_anchor=meld.rank_or_suit_anchor,
            slots=new_slots,
        )

    if meld.kind == MeldKind.SEQUENCE:
        suit, _anchor_start = _sequence_anchor(meld)
        if any(c.suit != suit for c in naturals):
            raise IllegalActionError(f"only {suit.value} cards fit into this sequence")

        combined = [*meld.slots, *cards]
        anchor_start, slots = _build_sequence_slots(combined)
        anchor = f"{suit.value}:{MELDABLE_RANKS[anchor_start].value}"
        return Meld(
            id=meld.id,
            team_id=meld.team_id,
            kind=meld.kind,
            rank_or_suit_anchor=anchor,
            slots=slots,
        )

    raise IllegalActionError(f"unknown meld kind {meld.kind}")


def steal_wild(
    meld: Meld, *, stealing_team_id: str, wild_card_id: str, replacement_card: Card
) -> tuple[Meld, Card]:
    """FR-17 / rules.md section 12. Returns (updated_meld, stolen_wild_card)."""
    if meld.team_id == stealing_team_id:
        raise IllegalActionError("cannot steal a wild from your own team's meld")
    if meld.kind == MeldKind.WILD_CANASTA:
        raise IllegalActionError("cannot steal from a wild canasta")
    if replacement_card.is_wild:
        raise IllegalActionError("the replacement card must be a natural card")

    try:
        pos = next(
            i
            for i, c in enumerate(meld.slots)
            if c is not None and c.id == wild_card_id
        )
    except StopIteration as exc:
        raise IllegalActionError("wild card not found in this meld") from exc

    stolen = meld.slots[pos]
    if stolen is None or not stolen.is_wild:
        raise IllegalActionError("target card is not a wild card")

    if meld.kind == MeldKind.SET:
        required_rank = Rank(meld.rank_or_suit_anchor)
        if replacement_card.rank != required_rank:
            raise IllegalActionError(f"replacement must be rank {required_rank.value}")
    else:  # SEQUENCE
        suit, anchor_start = _sequence_anchor(meld)
        required_rank = MELDABLE_RANKS[anchor_start + pos]
        if replacement_card.suit != suit or replacement_card.rank != required_rank:
            raise IllegalActionError(
                f"replacement must be {required_rank.value} of {suit.value} at this position"
            )

    new_slots = list(meld.slots)
    new_slots[pos] = replacement_card
    new_meld = Meld(
        id=meld.id,
        team_id=meld.team_id,
        kind=meld.kind,
        rank_or_suit_anchor=meld.rank_or_suit_anchor,
        slots=new_slots,
    )
    return new_meld, stolen
