#!/usr/bin/env python3
"""
Benchmark: top-tier bots only (50 games per matchup).
Skips simple / heuristic since their weakness is established.

Usage:
    cd backend
    python simulate_top.py [--games N] [--seed S]
"""
from __future__ import annotations

import os
import random
import sys
import time
from itertools import combinations
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.engine.actions import (
    AddToMeld, ConcedePenalty, CreateMeld, Discard, DrawDeck, DrawDiscard, StealWild,
)
from app.engine.engine import apply_action, final_deal_scores, start_new_deal
from app.engine.errors import IllegalActionError
from app.engine.turn_fsm import TurnPhase
from app.bots.strategy import (
    AdvancedBotStrategy,
    SequenceBotStrategy,
    EliteBotStrategy,
    FullPIMCBotStrategy,
    MLBotStrategy,
)


def _intent_to_action(intent: str, data: dict):
    match intent:
        case "draw_deck":      return DrawDeck()
        case "draw_discard":   return DrawDiscard()
        case "create_meld":    return CreateMeld(card_ids=data["card_ids"], wild_side=data.get("wild_side","low"))
        case "add_to_meld":    return AddToMeld(meld_id=data["meld_id"], card_ids=data["card_ids"], wild_side=data.get("wild_side","low"))
        case "steal_wild":     return StealWild(meld_id=data["meld_id"], wild_card_id=data["wild_card_id"], replacement_card_id=data["replacement_card_id"])
        case "discard":        return Discard(card_id=data["card_id"])
        case "concede_penalty":return ConcedePenalty()
        case _: raise ValueError(f"unknown intent {intent!r}")


def _fallback(deal, player_id):
    turn = deal.turn_state
    if turn.phase == TurnPhase.DRAW:
        return "draw_deck", {}
    if turn.must_meld_after_pickup and turn.melds_created_this_turn == 0 and not turn.pending_penalty:
        return "concede_penalty", {}
    hand = deal.hands[player_id]
    if hand:
        return "discard", {"card_id": hand[0].id}
    return "concede_penalty", {}


def simulate_game(strategies, player_order, player_team, rng, target=5000):
    team_scores = {t: 0 for t in set(player_team.values())}
    deal_number = 0

    while max(team_scores.values()) < target and deal_number < 60:
        fp   = player_order[deal_number % len(player_order)]
        deal = start_new_deal(player_order, player_team, dict(team_scores), rng=rng, first_player_id=fp)

        step = 0
        while not deal.deal_over and step < 600:
            pid  = deal.turn_state.current_player_id
            strat = strategies[pid]
            try:
                intent, data = strat.choose_intent(deal, pid)
            except Exception:
                intent, data = _fallback(deal, pid)

            try:
                deal = apply_action(deal, pid, _intent_to_action(intent, data))
            except Exception:
                try:
                    fi, fd = _fallback(deal, pid)
                    deal   = apply_action(deal, pid, _intent_to_action(fi, fd))
                except Exception:
                    break
            step += 1

        if deal.deal_over:
            bd = final_deal_scores(deal)
            for tid, b in bd.items():
                team_scores[tid] = team_scores.get(tid, 0) + b.total
        deal_number += 1

    winner = max(team_scores, key=team_scores.get)
    return winner, team_scores, deal_number


def run_matchup(name_a, strat_a, name_b, strat_b, n_games=50, target=5000, seed=42):
    player_order = ["a_p1","b_p1","a_p2","b_p2"]
    player_team  = {"a_p1": name_a, "a_p2": name_a, "b_p1": name_b, "b_p2": name_b}
    strategies   = {"a_p1": strat_a, "a_p2": strat_a, "b_p1": strat_b, "b_p2": strat_b}

    rng  = random.Random(seed)
    wins = {name_a: 0, name_b: 0}
    sc_a, sc_b = [], []
    total_deals = 0

    for _ in range(n_games):
        winner, scores, nd = simulate_game(strategies, player_order, player_team, rng, target)
        wins[winner] = wins.get(winner, 0) + 1
        sc_a.append(scores.get(name_a, 0))
        sc_b.append(scores.get(name_b, 0))
        total_deals += nd

    return {
        "name_a": name_a, "name_b": name_b,
        "wins_a": wins[name_a], "wins_b": wins[name_b],
        "avg_score_a": mean(sc_a), "avg_score_b": mean(sc_b),
        "avg_deals": total_deals / n_games,
    }


def main(n_games: int = 50, target: int = 5000, seed: int = 42) -> None:
    bots = [
        ("advanced",  AdvancedBotStrategy()),
        ("sequence",  SequenceBotStrategy()),
        ("elite",     EliteBotStrategy()),
        ("fullpimc",  FullPIMCBotStrategy()),
        ("mlbot",     MLBotStrategy()),
    ]

    matchups     = list(combinations(bots, 2))
    total_mu     = len(matchups)
    all_results  = []

    print(f"=== Top-Bot Tournament: {n_games} games each | target {target} | seed {seed} ===")
    print(f"Bots: {[n for n,_ in bots]}  |  Matchups: {total_mu}")
    print()

    t0 = time.perf_counter()
    for idx, ((na, sa), (nb, sb)) in enumerate(matchups, 1):
        print(f"[{idx:2d}/{total_mu}] {na:>10} vs {nb:<10}  ", end="", flush=True)
        t1  = time.perf_counter()
        r   = run_matchup(na, sa, nb, sb, n_games, target, seed)
        dt  = time.perf_counter() - t1
        all_results.append(r)
        pct = 100 * r["wins_a"] / n_games
        print(
            f"{r['wins_a']:3d}-{r['wins_b']:3d}"
            f"  ({pct:.0f}% {na})"
            f"  avg-deals {r['avg_deals']:.1f}"
            f"  {dt:.1f}s",
            flush=True,
        )

    total_elapsed = time.perf_counter() - t0

    # ── Leaderboard ───────────────────────────────────────────────────────────
    print()
    print("=" * 68)
    print(f"  TOP-BOT RESULTS  ({total_elapsed:.1f}s total)")
    print("=" * 68)
    print(f"  {'Bot':>10}  {'W':>4}  {'L':>4}  {'Win%':>6}  {'Avg score':>10}")
    print("-" * 68)

    stats: dict = {n: {"wins": 0, "losses": 0, "scores": []} for n, _ in bots}
    for r in all_results:
        a, b = r["name_a"], r["name_b"]
        stats[a]["wins"]   += r["wins_a"];  stats[a]["losses"] += r["wins_b"];  stats[a]["scores"].append(r["avg_score_a"])
        stats[b]["wins"]   += r["wins_b"];  stats[b]["losses"] += r["wins_a"];  stats[b]["scores"].append(r["avg_score_b"])

    ranked = sorted(stats.items(), key=lambda kv: kv[1]["wins"] / max(kv[1]["wins"]+kv[1]["losses"],1), reverse=True)
    for name, s in ranked:
        total = s["wins"] + s["losses"]
        pct   = 100 * s["wins"] / total if total else 0
        avg   = mean(s["scores"]) if s["scores"] else 0
        print(f"  {name:>10}  {s['wins']:>4}  {s['losses']:>4}  {pct:>5.1f}%  {avg:>10.0f}")

    print("=" * 68)
    print()
    print("Head-to-head matrix (row wins vs column, % win rate):")
    bot_names = [n for n, _ in bots]
    header = f"  {'':>10}" + "".join(f"  {n:>10}" for n in bot_names)
    print(header)
    for nr in bot_names:
        row = f"  {nr:>10}"
        for nc in bot_names:
            if nr == nc:
                row += f"  {'---':>10}"
            else:
                r = next(
                    (x for x in all_results if
                     (x["name_a"]==nr and x["name_b"]==nc) or
                     (x["name_a"]==nc and x["name_b"]==nr)),
                    None,
                )
                if r is None:
                    row += f"  {'?':>10}"
                elif r["name_a"] == nr:
                    row += f"  {100*r['wins_a']/n_games:>9.0f}%"
                else:
                    row += f"  {100*r['wins_b']/n_games:>9.0f}%"
        print(row)
    print()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=50)
    p.add_argument("--seed",  type=int, default=42)
    args = p.parse_args()
    main(args.games, seed=args.seed)
