"""Intent payloads accepted by apply_action (mirrors plan section 8 WS intents)."""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.models import MeldKind


@dataclass(frozen=True)
class DrawDeck:
    pass


@dataclass(frozen=True)
class DrawDiscard:
    pass


@dataclass(frozen=True)
class CreateMeld:
    kind: MeldKind
    card_ids: list[str]


@dataclass(frozen=True)
class AddToMeld:
    meld_id: str
    card_ids: list[str]


@dataclass(frozen=True)
class StealWild:
    meld_id: str
    wild_card_id: str
    replacement_card_id: str


@dataclass(frozen=True)
class Discard:
    card_id: str


@dataclass(frozen=True)
class ConcedePenalty:
    pass


Action = (
    DrawDeck
    | DrawDiscard
    | CreateMeld
    | AddToMeld
    | StealWild
    | Discard
    | ConcedePenalty
)
