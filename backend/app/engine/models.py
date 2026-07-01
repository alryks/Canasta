"""Pure data models for the canasta engine. No FastAPI/DB imports."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum


class Suit(str, Enum):
    SPADES = "SPADES"
    HEARTS = "HEARTS"
    DIAMONDS = "DIAMONDS"
    CLUBS = "CLUBS"


RED_SUITS = frozenset({Suit.HEARTS, Suit.DIAMONDS})


class Rank(str, Enum):
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"
    TWO = "2"
    JOKER = "JOKER"


# Ranks that can appear in a sequence, in order (ace is high only).
SEQUENCE_RANK_ORDER = [
    Rank.FOUR,
    Rank.FIVE,
    Rank.SIX,
    Rank.SEVEN,
    Rank.EIGHT,
    Rank.NINE,
    Rank.TEN,
    Rank.JACK,
    Rank.QUEEN,
    Rank.KING,
    Rank.ACE,
]

# Ranks that can anchor a natural meld (SET or SEQUENCE). Threes never meld;
# twos and jokers are always wild and can only appear as filler or as an
# all-wild WILD_CANASTA (rules.md section 3/9).
MELDABLE_RANKS = SEQUENCE_RANK_ORDER

WILD_RANKS = frozenset({Rank.TWO, Rank.JOKER})

_POINT_VALUES: dict[Rank, int] = {
    Rank.FOUR: 5,
    Rank.FIVE: 5,
    Rank.SIX: 5,
    Rank.SEVEN: 5,
    Rank.EIGHT: 5,
    Rank.NINE: 5,
    Rank.TEN: 10,
    Rank.JACK: 10,
    Rank.QUEEN: 10,
    Rank.KING: 10,
    Rank.ACE: 10,
    Rank.TWO: 10,
    Rank.JOKER: 50,
}

RED_THREE_BONUS = 100
BLACK_THREE_PENALTY = -100


@dataclass(frozen=True)
class Card:
    id: str
    rank: Rank
    suit: Suit | None  # None only for JOKER

    def __post_init__(self) -> None:
        if self.rank == Rank.JOKER and self.suit is not None:
            raise ValueError("JOKER must not have a suit")
        if self.rank != Rank.JOKER and self.suit is None:
            raise ValueError(f"non-JOKER card {self.rank} must have a suit")

    @property
    def is_wild(self) -> bool:
        return self.rank in WILD_RANKS

    @property
    def is_three(self) -> bool:
        return self.rank == Rank.THREE

    @property
    def is_red_three(self) -> bool:
        return self.is_three and self.suit in RED_SUITS

    @property
    def is_black_three(self) -> bool:
        return self.is_three and self.suit not in RED_SUITS

    @property
    def point_value(self) -> int:
        if self.rank == Rank.THREE:
            raise ValueError("threes have no meld point_value, they never enter melds")
        return _POINT_VALUES[self.rank]


def generate_deck() -> list[Card]:
    """Two standard 54-card decks (with jokers): 108 cards total.

    8 copies of every rank 3..Ace and 2 (2 decks x 4 suits), plus 4 jokers.
    """
    cards: list[Card] = []
    counter = itertools.count(1)

    non_joker_ranks = [
        Rank.THREE,
        Rank.FOUR,
        Rank.FIVE,
        Rank.SIX,
        Rank.SEVEN,
        Rank.EIGHT,
        Rank.NINE,
        Rank.TEN,
        Rank.JACK,
        Rank.QUEEN,
        Rank.KING,
        Rank.ACE,
        Rank.TWO,
    ]

    for _deck_copy in range(2):
        for rank in non_joker_ranks:
            for suit in Suit:
                cards.append(Card(id=f"c{next(counter)}", rank=rank, suit=suit))

    for _deck_copy in range(2):
        for _ in range(2):
            cards.append(Card(id=f"c{next(counter)}", rank=Rank.JOKER, suit=None))

    return cards


class MeldKind(str, Enum):
    SET = "SET"
    SEQUENCE = "SEQUENCE"
    WILD_CANASTA = "WILD_CANASTA"


class CanastaType(str, Enum):
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    WILD = "WILD"


CANASTA_BONUS: dict[CanastaType, int] = {
    CanastaType.CLEAN: 500,
    CanastaType.DIRTY: 200,
    CanastaType.WILD: 1000,
}

CANASTA_SIZE = 7


@dataclass
class Meld:
    id: str
    team_id: str
    kind: MeldKind
    rank_or_suit_anchor: (
        str  # rank value for SET, suit value for SEQUENCE, "" for WILD_CANASTA
    )
    slots: list[Card | None] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum(1 for c in self.slots if c is not None)

    @property
    def is_closed(self) -> bool:
        return self.size >= CANASTA_SIZE

    @property
    def natural_count(self) -> int:
        return sum(1 for c in self.slots if c is not None and not c.is_wild)

    @property
    def wild_count(self) -> int:
        return sum(1 for c in self.slots if c is not None and c.is_wild)

    @property
    def point_value(self) -> int:
        return sum(c.point_value for c in self.slots if c is not None)

    @property
    def canasta_type(self) -> CanastaType | None:
        if not self.is_closed:
            return None
        if self.kind == MeldKind.WILD_CANASTA:
            return CanastaType.WILD
        if self.wild_count == 0:
            return CanastaType.CLEAN
        return CanastaType.DIRTY

    @property
    def canasta_bonus(self) -> int:
        canasta_type = self.canasta_type
        if canasta_type is None:
            return 0
        return CANASTA_BONUS[canasta_type]

    @property
    def respects_wild_limit(self) -> bool:
        """Wilds may never outnumber naturals, except in a WILD_CANASTA."""
        if self.kind == MeldKind.WILD_CANASTA:
            return True
        return self.wild_count <= self.natural_count


# --- Opening threshold table (section 10) ---

_THRESHOLD_TABLE: list[tuple[int, int]] = [
    (0, 30),
    (1000, 60),
    (2000, 90),
    (3000, 120),
    (4000, 150),
]


def opening_threshold(team_score: int) -> int:
    """Minimum meld points required for a team's first meld this deal."""
    threshold = _THRESHOLD_TABLE[0][1]
    for min_score, value in _THRESHOLD_TABLE:
        if team_score >= min_score:
            threshold = value
        else:
            break
    return threshold


@dataclass
class TeamTable:
    team_id: str
    melds: list[Meld] = field(default_factory=list)
    is_opened: bool = False
    turn_accumulator: int = 0
