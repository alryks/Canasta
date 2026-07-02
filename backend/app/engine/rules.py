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


def _build_sequence_slots(
    cards: list[Card],
    *,
    wild_side: str = "low",
    preferred_wild_positions: dict[str, int] | None = None,
) -> tuple[int, list[Card]]:
    """Fit `cards` (single suit, distinct natural ranks + wild fillers) into a
    contiguous window of MELDABLE_RANKS. Returns (anchor_start, ordered slots).

    `wild_side` decides where wilds that don't bridge an internal gap end up:
    "low" extends the window toward 4, "high" toward the Ace (FR: the player
    picks the side). `preferred_wild_positions` (card id -> absolute rank
    index) keeps wilds already sitting in the meld at their old rank when the
    meld is rebuilt by add_to_meld, so adding cards never silently teleports
    an existing wild to the other end.
    """
    if wild_side not in ("low", "high"):
        raise IllegalActionError(f"wild_side must be 'low' or 'high', got {wild_side!r}")
    preferred = preferred_wild_positions or {}

    naturals, wilds = _split_wild_natural(cards)
    if not naturals:
        raise IllegalActionError("a sequence needs at least one natural card")
    if any(c.rank not in MELDABLE_RANKS for c in naturals):
        raise IllegalActionError("threes can never be part of a meld")

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
    if len(cards) < window_needed:
        raise IllegalActionError(
            "not enough wild cards to bridge the gaps in this sequence"
        )

    # Every anchor in [start_min, start_max] yields a window covering all
    # naturals; the choice between them is exactly the low/high wild placement.
    start_min = max(0, high - (len(cards) - 1))
    start_max = min(low, len(MELDABLE_RANKS) - len(cards))
    if start_min > start_max:
        raise IllegalActionError("sequence would have to run past 4 or past Ace")

    natural_positions = set(indices)

    def satisfied_count(start: int) -> int:
        window = range(start, start + len(cards))
        return sum(
            1
            for pos in preferred.values()
            if pos in window and pos not in natural_positions
        )

    candidates = range(start_min, start_max + 1)
    best_satisfied = max(satisfied_count(s) for s in candidates)
    ties = [s for s in candidates if satisfied_count(s) == best_satisfied]
    anchor_start = max(ties) if wild_side == "high" else min(ties)

    slots: list[Card | None] = [None] * len(cards)
    for card in naturals:
        slots[MELDABLE_RANKS.index(card.rank) - anchor_start] = card

    remaining_wilds = []
    for card in wilds:
        pos = preferred.get(card.id)
        rel = pos - anchor_start if pos is not None else None
        if rel is not None and 0 <= rel < len(cards) and slots[rel] is None:
            slots[rel] = card
        else:
            remaining_wilds.append(card)
    free = [i for i in range(len(cards)) if slots[i] is None]
    for rel, card in zip(free, remaining_wilds):
        slots[rel] = card

    return anchor_start, [c for c in slots if c is not None]


def build_new_meld(
    meld_id: str, team_id: str, cards: list[Card], *, wild_side: str = "low"
) -> Meld:
    """Infer SET vs SEQUENCE vs WILD_CANASTA from the cards themselves.

    Given the wild<=natural constraint, a legal meld of size>=3 always has
    >=2 natural cards whenever it contains a wild (1 natural would allow at
    most 1 wild -> 2 cards, below the minimum). With >=2 naturals, "same
    rank" (a SET) and "same suit + all distinct ranks" (a SEQUENCE) are
    mutually exclusive, so the kind never needs to be supplied explicitly.
    """
    if len(cards) < 3:
        raise IllegalActionError("a new meld needs at least 3 cards")

    naturals, wilds = _split_wild_natural(cards)

    if not naturals:
        return Meld(
            id=meld_id,
            team_id=team_id,
            kind=MeldKind.WILD_CANASTA,
            rank_or_suit_anchor="",
            slots=list(cards),
        )

    if len(wilds) > len(naturals):
        raise IllegalActionError(
            "wild cards cannot outnumber natural cards in this meld"
        )

    ranks = {c.rank for c in naturals}
    suits = {c.suit for c in naturals}
    can_be_set = len(ranks) == 1 and next(iter(ranks)) in MELDABLE_RANKS
    can_be_sequence = False
    sequence_result: tuple[int, list[Card]] | None = None
    if len(suits) == 1 and len(ranks) == len(naturals):
        try:
            sequence_result = _build_sequence_slots(cards, wild_side=wild_side)
            can_be_sequence = True
        except IllegalActionError:
            can_be_sequence = False

    if can_be_set:
        rank = next(iter(ranks))
        return Meld(
            id=meld_id,
            team_id=team_id,
            kind=MeldKind.SET,
            rank_or_suit_anchor=rank.value,
            slots=list(cards),
        )

    if can_be_sequence:
        assert sequence_result is not None
        anchor_start, slots = sequence_result
        suit = next(iter(suits))
        anchor = f"{suit.value}:{MELDABLE_RANKS[anchor_start].value}"
        return Meld(
            id=meld_id,
            team_id=team_id,
            kind=MeldKind.SEQUENCE,
            rank_or_suit_anchor=anchor,
            slots=slots,
        )

    raise IllegalActionError(
        "cards do not form a valid set (same rank) or sequence (same suit, consecutive ranks)"
    )


def _sequence_anchor(meld: Meld) -> tuple[Suit, int]:
    suit_value, start_rank_value = meld.rank_or_suit_anchor.split(":")
    return Suit(suit_value), MELDABLE_RANKS.index(Rank(start_rank_value))


def add_to_meld(
    meld: Meld, team_id: str, cards: list[Card], *, wild_side: str = "low"
) -> Meld:
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
        suit, old_anchor_start = _sequence_anchor(meld)
        if any(c.suit != suit for c in naturals):
            raise IllegalActionError(f"only {suit.value} cards fit into this sequence")

        # Pin wilds already in the meld to their current ranks so only the
        # newly added wilds move to the requested side.
        preferred = {
            c.id: old_anchor_start + i
            for i, c in enumerate(meld.slots)
            if c is not None and c.is_wild
        }
        combined = [*meld.slots, *cards]
        anchor_start, slots = _build_sequence_slots(
            combined, wild_side=wild_side, preferred_wild_positions=preferred
        )
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
