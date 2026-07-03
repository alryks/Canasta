#!/usr/bin/env python3
"""
v6 training: append seq-vs-elite data to existing cache, retrain.

Motivation: MLBot gets 48% vs Sequence (worse than Elite v5 at 55%).
Root cause: training data had no elite-vs-sequence matchup so the model
doesn't learn to handle Sequence's rapid canasta-building patterns.

Fix: generate 300 games of seq-vs-elite and append to existing 495k samples.
Expected: ~90k extra samples, total ~585k, retrains in ~15 min.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score

from app.engine.engine import start_new_deal, apply_action, final_deal_scores
from app.engine.turn_fsm import TurnPhase
from app.bots.strategy import (
    SequenceBotStrategy,
    EliteBotStrategy,
    _fallback_move,
    _exec_intent,
)
from app.bots.value_model import extract_features, N_FEATURES, WEIGHTS_PATH

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_train_cache.npz")


def _run_matchup_games(strat_a, strat_b, n_games, seed):
    player_order = ["p0", "p1", "p2", "p3"]
    player_team  = {"p0": "A", "p2": "A", "p1": "B", "p3": "B"}
    strategies   = {"p0": strat_a, "p2": strat_a, "p1": strat_b, "p3": strat_b}
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
    print("=== Canasta Value Function Training v6 (append seq-vs-elite) ===")

    # 1. Load existing cache
    if not os.path.exists(CACHE):
        print(f"ERROR: Cache not found at {CACHE}. Run train_value_model.py first.")
        sys.exit(1)

    data = np.load(CACHE)
    X_old, y_old = data["X"], data["y"]
    print(f"Loaded cache: {X_old.shape[0]:,} samples ({X_old.shape[1]} features)")

    if X_old.shape[1] != N_FEATURES:
        print(f"ERROR: Cache has {X_old.shape[1]} features but model expects {N_FEATURES}.")
        sys.exit(1)

    # 2. Generate new data: seq vs elite (both team perspectives captured per game)
    new_samples = []
    for desc, sa, sb, seed, n in [
        ("seq vs elite",  SequenceBotStrategy(), EliteBotStrategy(),    41, 400),
    ]:
        print(f"  {desc}: {n} games …", end=" ", flush=True)
        t0 = time.perf_counter()
        X_new, y_new = _run_matchup_games(sa, sb, n, seed)
        new_samples.append((X_new, y_new))
        print(f"{len(X_new):,} samples  ({time.perf_counter()-t0:.1f}s)", flush=True)

    # 3. Combine
    all_X = list(X_old) + [row for (X, _) in new_samples for row in X]
    all_y = list(y_old) + [lbl for (_, y) in new_samples for lbl in y]
    X = np.array(all_X, dtype=np.float32)
    y = np.array(all_y, dtype=np.float32)

    # Save expanded cache
    np.savez_compressed(CACHE, X=X, y=y)
    print(f"\nExpanded dataset: {X.shape[0]:,} samples  |  win rate: {y.mean():.3f}")

    # 4. Train (holdout eval + full retrain)
    print("\nTraining MLPClassifier (128-64 hidden, sigmoid output) …")
    y_lbl = (y > 0.5).astype(int)
    split = int(0.9 * len(X))
    X_tr, X_val = X[:split], X[split:]
    y_tr,  y_val = y_lbl[:split], y_lbl[split:]

    scaler = StandardScaler()
    X_tr_sc  = scaler.fit_transform(X_tr)
    X_val_sc = scaler.transform(X_val)

    clf = MLPClassifier(
        hidden_layer_sizes=(128, 64), activation="relu", solver="adam",
        learning_rate_init=2e-4, batch_size=512, max_iter=300,
        random_state=0, early_stopping=True, n_iter_no_change=20,
        validation_fraction=0.1,
    )
    clf.fit(X_tr_sc, y_tr)

    y_pred_p = clf.predict_proba(X_val_sc)[:, 1]
    auc = roc_auc_score(y_val, y_pred_p)
    acc = accuracy_score(y_val, (y_pred_p > 0.5).astype(int))
    print(f"Holdout AUC: {auc:.4f}  |  Acc: {acc:.4f}  (n={len(y_val):,})")

    # Full retrain
    scaler2 = StandardScaler(); X_sc = scaler2.fit_transform(X)
    clf2 = MLPClassifier(
        hidden_layer_sizes=(128, 64), activation="relu", solver="adam",
        learning_rate_init=2e-4, batch_size=512, max_iter=300,
        random_state=0, early_stopping=True, n_iter_no_change=20,
        validation_fraction=0.1,
    )
    clf2.fit(X_sc, y_lbl)

    payload = _export_mlp_classifier(clf2, scaler2)
    os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
    with open(WEIGHTS_PATH, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = os.path.getsize(WEIGHTS_PATH) / 1024
    print(f"\nWeights saved -> {WEIGHTS_PATH}  ({size_kb:.1f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
