"""End-of-deal scoring (rules.md section 14, plan FR-27)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.engine.models import (
    BLACK_THREE_PENALTY,
    RED_THREE_BONUS,
    Card,
    TeamTable,
)


class ExitType(str, Enum):
    CLEAN = "CLEAN"  # last card goes into a meld, no discard (+400)
    DIRTY = "DIRTY"  # last card goes to the discard pile (+200)


EXIT_BONUS: dict[ExitType, int] = {
    ExitType.CLEAN: 400,
    ExitType.DIRTY: 200,
}


@dataclass(frozen=True)
class DealScoreBreakdown:
    table_points: int  # signed: positive if team closed >=1 canasta, else negative
    canasta_bonus: int
    hand_penalty: int  # always <= 0
    three_bonus: int  # red threes (+100 each) minus black threes (100 each)
    exit_bonus: int
    total: int


def score_team_deal(
    team_table: TeamTable,
    hand_cards: list[Card],
    *,
    went_out: bool,
    exit_type: ExitType | None = None,
) -> DealScoreBreakdown:
    has_canasta = any(meld.is_closed for meld in team_table.melds)
    table_points_raw = sum(meld.point_value for meld in team_table.melds)
    table_points = table_points_raw if has_canasta else -table_points_raw
    canasta_bonus = sum(meld.canasta_bonus for meld in team_table.melds)

    non_three_cards = [c for c in hand_cards if not c.is_three]
    hand_penalty = -sum(c.point_value for c in non_three_cards)

    red_threes = sum(1 for c in hand_cards if c.is_red_three)
    black_threes = sum(1 for c in hand_cards if c.is_black_three)
    three_bonus = red_threes * RED_THREE_BONUS + black_threes * BLACK_THREE_PENALTY

    exit_bonus = 0
    if went_out:
        if exit_type is None:
            raise ValueError("exit_type is required when went_out is True")
        exit_bonus = EXIT_BONUS[exit_type]

    total = table_points + canasta_bonus + hand_penalty + three_bonus + exit_bonus
    return DealScoreBreakdown(
        table_points=table_points,
        canasta_bonus=canasta_bonus,
        hand_penalty=hand_penalty,
        three_bonus=three_bonus,
        exit_bonus=exit_bonus,
        total=total,
    )


def score_deal(
    team_tables: dict[str, TeamTable],
    team_hands: dict[str, list[Card]],
    *,
    went_out_team_id: str | None,
    exit_type: ExitType | None = None,
) -> dict[str, DealScoreBreakdown]:
    """Score every team at the end of a deal. `team_hands` = combined hand
    cards of both players on that team."""
    return {
        team_id: score_team_deal(
            team_table,
            team_hands[team_id],
            went_out=(team_id == went_out_team_id),
            exit_type=exit_type,
        )
        for team_id, team_table in team_tables.items()
    }
