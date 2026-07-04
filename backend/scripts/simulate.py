#!/usr/bin/env python3
"""Simulate 100 games for every pair of bot strategies.

Run from anywhere:
    python backend/scripts/simulate.py
"""

from __future__ import annotations

import os
import random
import sys
import time
from itertools import combinations
from statistics import mean, stdev

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine.actions import (
    AddToMeld,
    ConcedePenalty,
    CreateMeld,
    Discard,
    DrawDeck,
    DrawDiscard,
    StealWild,
)
from app.engine.engine import apply_action, final_deal_scores, start_new_deal
from app.engine.errors import IllegalActionError
from app.engine.turn_fsm import TurnPhase
from app.bots.strategy import (
    SimpleBotStrategy,
    HeuristicBotStrategy,
    AdvancedBotStrategy,
    SequenceBotStrategy,
    EliteBotStrategy,
    FullPIMCBotStrategy,
    MLBotStrategy,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _intent_to_action(intent: str, data: dict):
    match intent:
        case "draw_deck":
            return DrawDeck()
        case "draw_discard":
            return DrawDiscard()
        case "create_meld":
            return CreateMeld(
                card_ids=data["card_ids"], wild_side=data.get("wild_side", "low")
            )
        case "add_to_meld":
            return AddToMeld(
                meld_id=data["meld_id"],
                card_ids=data["card_ids"],
                wild_side=data.get("wild_side", "low"),
            )
        case "steal_wild":
            return StealWild(
                meld_id=data["meld_id"],
                wild_card_id=data["wild_card_id"],
                replacement_card_id=data["replacement_card_id"],
            )
        case "discard":
            return Discard(card_id=data["card_id"])
        case "concede_penalty":
            return ConcedePenalty()
        case _:
            raise ValueError(f"unknown intent {intent!r}")


def _fallback(deal, player_id):
    turn = deal.turn_state
    if turn.phase == TurnPhase.DRAW:
        return "draw_deck", {}
    if (
        turn.must_meld_after_pickup
        and turn.melds_created_this_turn == 0
        and not turn.pending_penalty
    ):
        return "concede_penalty", {}
    hand = deal.hands[player_id]
    if hand:
        return "discard", {"card_id": hand[0].id}
    return "concede_penalty", {}


def simulate_game(
    strategies: dict,
    player_order: list[str],
    player_team: dict[str, str],
    rng: random.Random,
    target_score: int = 5000,
) -> tuple[str, dict[str, int], int]:
    team_scores: dict[str, int] = {t: 0 for t in set(player_team.values())}
    deal_number = 0

    while max(team_scores.values()) < target_score and deal_number < 60:
        first_player = player_order[deal_number % len(player_order)]
        deal = start_new_deal(
            player_order,
            player_team,
            dict(team_scores),
            rng=rng,
            first_player_id=first_player,
        )

        step = 0
        while not deal.deal_over and step < 600:
            pid = deal.turn_state.current_player_id
            strategy = strategies[pid]

            try:
                intent, data = strategy.choose_intent(deal, pid)
            except Exception:
                intent, data = _fallback(deal, pid)

            try:
                action = _intent_to_action(intent, data)
                deal = apply_action(deal, pid, action)
            except (IllegalActionError, ValueError, Exception):
                try:
                    fb_i, fb_d = _fallback(deal, pid)
                    deal = apply_action(deal, pid, _intent_to_action(fb_i, fb_d))
                except Exception:
                    break

            step += 1

        if deal.deal_over:
            breakdown = final_deal_scores(deal)
            for tid, bd in breakdown.items():
                team_scores[tid] = team_scores.get(tid, 0) + bd.total

        deal_number += 1

    winner = max(team_scores, key=team_scores.get)
    return winner, team_scores, deal_number


def run_matchup(
    name_a: str,
    strat_a,
    name_b: str,
    strat_b,
    n_games: int = 100,
    target: int = 5000,
    seed: int = 42,
) -> dict:
    player_order = ["a_p1", "b_p1", "a_p2", "b_p2"]
    player_team = {
        "a_p1": name_a, "a_p2": name_a,
        "b_p1": name_b, "b_p2": name_b,
    }
    strategies = {
        "a_p1": strat_a, "a_p2": strat_a,
        "b_p1": strat_b, "b_p2": strat_b,
    }

    rng = random.Random(seed)
    wins = {name_a: 0, name_b: 0}
    scores_a, scores_b = [], []
    total_deals = 0

    for _ in range(n_games):
        winner, scores, n_deals = simulate_game(
            strategies, player_order, player_team, rng, target
        )
        wins[winner] = wins.get(winner, 0) + 1
        scores_a.append(scores.get(name_a, 0))
        scores_b.append(scores.get(name_b, 0))
        total_deals += n_deals

    return {
        "name_a": name_a,
        "name_b": name_b,
        "wins_a": wins[name_a],
        "wins_b": wins[name_b],
        "avg_score_a": mean(scores_a),
        "avg_score_b": mean(scores_b),
        "avg_deals": total_deals / n_games,
    }


def main(n_games: int = 100, target: int = 5000, seed: int = 42) -> None:
    bots = [
        ("simple",    SimpleBotStrategy()),
        ("heuristic", HeuristicBotStrategy()),
        ("advanced",  AdvancedBotStrategy()),
        ("sequence",  SequenceBotStrategy()),
        ("elite",     EliteBotStrategy()),
        ("fullpimc",  FullPIMCBotStrategy()),
        ("mlbot",     MLBotStrategy()),
    ]

    matchups = list(combinations(bots, 2))
    total_matchups = len(matchups)

    print(f"=== Canasta bot tournament: {n_games} games each, target {target} ===")
    print(f"Matchups: {total_matchups}  |  seed: {seed}")
    print()

    all_results = []

    t0 = time.perf_counter()
    for idx, ((name_a, strat_a), (name_b, strat_b)) in enumerate(matchups, 1):
        print(f"[{idx}/{total_matchups}] {name_a:>10} vs {name_b:<10}  ", end="", flush=True)
        t1 = time.perf_counter()
        r = run_matchup(name_a, strat_a, name_b, strat_b, n_games, target, seed)
        elapsed = time.perf_counter() - t1
        all_results.append(r)
        pct = 100 * r["wins_a"] / n_games
        print(
            f"{r['wins_a']:3d}-{r['wins_b']:3d}  "
            f"({pct:.0f}% {name_a})  "
            f"avg-deals {r['avg_deals']:.1f}  "
            f"{elapsed:.1f}s"
        )

    total_elapsed = time.perf_counter() - t0

    # ── Leaderboard ──────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"  TOURNAMENT RESULTS  ({total_elapsed:.1f}s total)")
    print("=" * 60)
    print(f"  {'Bot':>10}  {'Wins':>6}  {'Losses':>7}  {'Win%':>6}  {'Avg score':>10}")
    print("-" * 60)

    stats: dict[str, dict] = {name: {"wins": 0, "losses": 0, "scores": []} for name, _ in bots}
    for r in all_results:
        a, b = r["name_a"], r["name_b"]
        stats[a]["wins"] += r["wins_a"]
        stats[a]["losses"] += r["wins_b"]
        stats[a]["scores"].extend([r["avg_score_a"]])
        stats[b]["wins"] += r["wins_b"]
        stats[b]["losses"] += r["wins_a"]
        stats[b]["scores"].extend([r["avg_score_b"]])

    ranked = sorted(
        stats.items(),
        key=lambda kv: kv[1]["wins"] / max(kv[1]["wins"] + kv[1]["losses"], 1),
        reverse=True,
    )
    for name, s in ranked:
        total = s["wins"] + s["losses"]
        pct = 100 * s["wins"] / total if total else 0
        avg_score = mean(s["scores"]) if s["scores"] else 0
        print(
            f"  {name:>10}  {s['wins']:>6}  {s['losses']:>7}  "
            f"{pct:>5.1f}%  {avg_score:>10.0f}"
        )

    print("=" * 60)
    print()
    print("Head-to-head matrix (row beats column, % wins):")
    bot_names = [n for n, _ in bots]
    header = f"  {'':>10}" + "".join(f"  {n:>10}" for n in bot_names)
    print(header)
    for name_r in bot_names:
        row = f"  {name_r:>10}"
        for name_c in bot_names:
            if name_r == name_c:
                row += f"  {'---':>10}"
            else:
                # Find result
                r = next(
                    (x for x in all_results
                     if (x["name_a"] == name_r and x["name_b"] == name_c)
                     or (x["name_a"] == name_c and x["name_b"] == name_r)),
                    None,
                )
                if r is None:
                    row += f"  {'?':>10}"
                elif r["name_a"] == name_r:
                    pct = 100 * r["wins_a"] / n_games
                    row += f"  {pct:>9.0f}%"
                else:
                    pct = 100 * r["wins_b"] / n_games
                    row += f"  {pct:>9.0f}%"
        print(row)
    print()


if __name__ == "__main__":
    main()
