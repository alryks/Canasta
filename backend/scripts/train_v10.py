#!/usr/bin/env python3
"""
v10 training: fix Advanced-matchup instability + diversify human-partner proxy.

Problem observed v8->v9: MLBot vs Advanced dropped 72%->52%. The training cache
has never included a *direct* fullpimc-vs-advanced matchup (v6 cache only had
seq/adv, elite/adv, elite/elite, seq/elite) — the model has been generalizing
to Advanced positions indirectly. Also, v9's human-partnership data used only
AdvancedBotStrategy as the "human" proxy; real human skill varies more widely,
so this adds a weaker proxy (HeuristicBotStrategy) too.

New data added on top of v9's 826k cache:
  1. fullpimc vs advanced (300 games)              — direct signal, missing until now
  2. [fullpimc+heuristic] vs [seq+seq] (200)        — weaker human-partner proxy vs Sequence
  3. [fullpimc+heuristic] vs [elite+elite] (150)    — weaker human-partner proxy vs strong opp

Architecture: 128-64 (proven), lr=2e-4 (proven). Checkpointed per matchup batch
so a killed process can resume without regenerating data.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score

from app.engine.engine import start_new_deal, final_deal_scores
from app.engine.turn_fsm import TurnPhase
from app.bots.strategy import (
    AdvancedBotStrategy, HeuristicBotStrategy, SequenceBotStrategy,
    EliteBotStrategy, FullPIMCBotStrategy,
    _fallback_move, _exec_intent,
)
from app.bots.value_model import extract_features, N_FEATURES, WEIGHTS_PATH

CACHE = os.path.join(BACKEND_DIR, "_train_cache.npz")


def _run_matchup(strat_p0, strat_p2, strat_p1, strat_p3, n_games, seed):
    """Run games with per-player strategies (supports mixed-quality teams)."""
    player_order = ["p0", "p1", "p2", "p3"]
    player_team  = {"p0": "A", "p2": "A", "p1": "B", "p3": "B"}
    strategies   = {"p0": strat_p0, "p2": strat_p2, "p1": strat_p1, "p3": strat_p3}
    rng = random.Random(seed)
    X, y = [], []

    for _ in range(n_games):
        team_scores = {"A": 0, "B": 0}
        deal_num = 0
        while max(team_scores.values()) < 5000 and deal_num < 50:
            fp   = player_order[deal_num % 4]
            deal = start_new_deal(
                player_order, player_team, dict(team_scores),
                rng=rng, first_player_id=fp,
            )
            snaps, step = [], 0
            while not deal.deal_over and step < 600:
                pid   = deal.turn_state.current_player_id
                phase = deal.turn_state.phase
                if phase == TurnPhase.DRAW:
                    try:
                        snaps.append((extract_features(deal, pid), deal.player_team[pid]))
                    except Exception:
                        pass
                try:
                    intent, data = strategies[pid].choose_intent(deal, pid)
                except Exception:
                    intent, data = _fallback_move(deal, pid)
                try:
                    deal = _exec_intent(deal, pid, intent, data)
                except Exception:
                    try:
                        deal = _exec_intent(deal, pid, *_fallback_move(deal, pid))
                    except Exception:
                        break
                step += 1

            if deal.deal_over:
                try:
                    scores = final_deal_scores(deal)
                    for feats, team_id in snaps:
                        opp_id = next(t for t in deal.teams if t != team_id)
                        delta  = scores[team_id].total - scores[opp_id].total
                        label  = 1.0 if delta > 0 else (0.5 if delta == 0 else 0.0)
                        X.append(feats); y.append(label)
                    for tid, bd in scores.items():
                        team_scores[tid] = team_scores.get(tid, 0) + bd.total
                except Exception:
                    pass
            deal_num += 1
    return X, y


def _export_mlp_classifier(model, scaler):
    coefs, intercepts = model.coefs_, model.intercepts_
    mean_, scale_ = scaler.mean_, scaler.scale_
    W0_scaled = coefs[0] / scale_[:, np.newaxis]
    b0_scaled = intercepts[0] - (mean_ / scale_) @ coefs[0]
    layers = []
    for i, (W, b) in enumerate(zip(coefs, intercepts)):
        layers.append({
            "W": (W0_scaled if i == 0 else W).T.tolist(),
            "b": (b0_scaled if i == 0 else b).tolist(),
        })
    return {"type": "mlp_classifier", "layers": layers}


def main():
    print("=== Canasta Value Function Training v10 ===")
    print("    Fix Advanced-matchup instability + diversify human-partner proxy")
    print()

    if not os.path.exists(CACHE):
        print(f"ERROR: Cache not found at {CACHE}.")
        sys.exit(1)

    data = np.load(CACHE)
    X_old, y_old = data["X"], data["y"]
    print(f"Loaded cache: {X_old.shape[0]:,} samples ({X_old.shape[1]} features)")

    if X_old.shape[1] != N_FEATURES:
        print(f"ERROR: Cache has {X_old.shape[1]} features but model expects {N_FEATURES}.")
        sys.exit(1)

    fp  = FullPIMCBotStrategy()
    heu = HeuristicBotStrategy()
    seq = SequenceBotStrategy()
    eli = EliteBotStrategy()
    adv = AdvancedBotStrategy()

    CACHE_DIR = os.path.dirname(CACHE)
    matchups = [
        # (key, desc, p0, p2, p1, p3, n_games, seed)
        ("fp_vs_adv",     "fullpimc vs advanced       ", fp,  fp,  adv, adv, 300, 201),
        ("fpheu_vs_seq",  "[fp+heuristic] vs [seq+seq]", fp,  heu, seq, seq, 200, 202),
        ("fpheu_vs_eli",  "[fp+heuristic] vs [eli+eli]", fp,  heu, eli, eli, 150, 203),
    ]

    new_X, new_y = [], []
    for key, desc, p0, p2, p1, p3, n, seed in matchups:
        ckpt = os.path.join(CACHE_DIR, f"_v10_ckpt_{key}.npz")
        if os.path.exists(ckpt):
            d = np.load(ckpt)
            cx, cy = d["X"].tolist(), d["y"].tolist()
            new_X.extend(cx); new_y.extend(cy)
            print(f"  {desc}: loaded checkpoint  {len(cx):,} samples", flush=True)
            continue
        print(f"  {desc}: {n} games …", end=" ", flush=True)
        t0 = time.perf_counter()
        X_b, y_b = _run_matchup(p0, p2, p1, p3, n, seed)
        np.savez_compressed(ckpt, X=np.array(X_b, dtype=np.float32), y=np.array(y_b, dtype=np.float32))
        new_X.extend(X_b); new_y.extend(y_b)
        print(f"{len(X_b):,} samples  ({time.perf_counter()-t0:.1f}s)", flush=True)

    # Combine and save expanded cache
    X = np.array(list(X_old) + new_X, dtype=np.float32)
    y = np.array(list(y_old) + new_y, dtype=np.float32)
    np.savez_compressed(CACHE, X=X, y=y)
    print(f"\nExpanded dataset: {X.shape[0]:,} samples  |  win rate: {y.mean():.3f}")

    # Train 128-64 (proven architecture)
    print("\nTraining MLPClassifier (128-64 hidden) …")
    y_lbl = (y > 0.5).astype(int)
    split = int(0.9 * len(X))
    X_tr, X_val = X[:split], X[split:]
    y_tr,  y_val = y_lbl[:split], y_lbl[split:]

    scaler = StandardScaler()
    X_tr_sc  = scaler.fit_transform(X_tr)
    X_val_sc = scaler.transform(X_val)

    t0 = time.perf_counter()
    clf = MLPClassifier(
        hidden_layer_sizes=(128, 64), activation="relu", solver="adam",
        learning_rate_init=2e-4, batch_size=512, max_iter=300,
        random_state=0, early_stopping=True, n_iter_no_change=20,
        validation_fraction=0.1,
    )
    clf.fit(X_tr_sc, y_tr)
    print(f"  Train time: {time.perf_counter()-t0:.1f}s  |  Iterations: {clf.n_iter_}")

    y_pred_p = clf.predict_proba(X_val_sc)[:, 1]
    auc = roc_auc_score(y_val, y_pred_p)
    acc = accuracy_score(y_val, (y_pred_p > 0.5).astype(int))
    print(f"Holdout AUC: {auc:.4f}  |  Acc: {acc:.4f}  (n={len(y_val):,})")

    # Full retrain
    print("\nFull retrain …")
    t0 = time.perf_counter()
    scaler2 = StandardScaler(); X_sc = scaler2.fit_transform(X)
    clf2 = MLPClassifier(
        hidden_layer_sizes=(128, 64), activation="relu", solver="adam",
        learning_rate_init=2e-4, batch_size=512, max_iter=300,
        random_state=0, early_stopping=True, n_iter_no_change=20,
        validation_fraction=0.1,
    )
    clf2.fit(X_sc, y_lbl)
    print(f"  Retrain time: {time.perf_counter()-t0:.1f}s  |  Iterations: {clf2.n_iter_}")

    payload = _export_mlp_classifier(clf2, scaler2)
    os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
    with open(WEIGHTS_PATH, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = os.path.getsize(WEIGHTS_PATH) / 1024
    print(f"\nWeights saved -> {WEIGHTS_PATH}  ({size_kb:.1f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
