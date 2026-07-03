#!/usr/bin/env python3
"""
Train a positional value function for Canasta (Iteration 2).

Changes from v1:
  - Classification target: P(our team wins this deal) instead of score-delta regression
  - Diverse training data: 3 different bot matchups to avoid distribution shift
  - Metric: AUC instead of RMSE
  - Model output [0,1] converted at inference to (-SCALE, +SCALE) EV

Usage:
    cd backend
    python train_value_model.py [--games N]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

from app.engine.engine import start_new_deal, apply_action, final_deal_scores
from app.engine.errors import IllegalActionError
from app.engine.turn_fsm import TurnPhase
from app.bots.strategy import (
    AdvancedBotStrategy,
    SequenceBotStrategy,
    EliteBotStrategy,
    _fallback_move,
    _exec_intent,
)
from app.bots.value_model import extract_features, N_FEATURES, WEIGHTS_PATH

DEFAULT_GAMES_PER_MATCHUP = 500


# ── Data generation ───────────────────────────────────────────────────────────

def _run_matchup_games(
    strat_a, strat_b, n_games: int, seed: int
) -> tuple[list[list[float]], list[float]]:
    """Play n_games with strat_a as team A and strat_b as team B.
    Records (features, win_label) at every DRAW phase."""
    player_order = ["p0", "p1", "p2", "p3"]
    player_team  = {"p0": "A", "p2": "A", "p1": "B", "p3": "B"}
    strategies   = {"p0": strat_a, "p2": strat_a, "p1": strat_b, "p3": strat_b}

    rng = random.Random(seed)
    X: list[list[float]] = []
    y: list[float] = []

    for game_idx in range(n_games):
        team_scores: dict[str, int] = {"A": 0, "B": 0}
        deal_num = 0

        while max(team_scores.values()) < 5000 and deal_num < 50:
            fp   = player_order[deal_num % 4]
            deal = start_new_deal(
                player_order, player_team, dict(team_scores),
                rng=rng, first_player_id=fp,
            )

            snaps: list[tuple[list[float], str]] = []
            step = 0

            while not deal.deal_over and step < 600:
                pid   = deal.turn_state.current_player_id
                phase = deal.turn_state.phase

                if phase == TurnPhase.DRAW:
                    try:
                        feats = extract_features(deal, pid)
                        snaps.append((feats, deal.player_team[pid]))
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
                        fi, fd = _fallback_move(deal, pid)
                        deal   = _exec_intent(deal, pid, fi, fd)
                    except Exception:
                        break
                step += 1

            if deal.deal_over:
                try:
                    scores = final_deal_scores(deal)
                    for feats, team_id in snaps:
                        opp_id = next(t for t in deal.teams if t != team_id)
                        delta  = scores[team_id].total - scores[opp_id].total
                        # Binary classification: did our team win this deal?
                        label  = 1.0 if delta > 0 else (0.5 if delta == 0 else 0.0)
                        X.append(feats)
                        y.append(label)

                    for tid, bd in scores.items():
                        team_scores[tid] = team_scores.get(tid, 0) + bd.total
                except Exception:
                    pass

            deal_num += 1

    return X, y


def _generate_data(n_per_matchup: int) -> tuple[np.ndarray, np.ndarray]:
    """Collect training data from three diverse matchups.

    Matchup selection (v3): drop weak seq-vs-seq (low-quality positions),
    replace with elite-vs-elite (high-quality positions that better reflect
    the states where EliteBot/FullPIMC/MLBot will actually call the model).
    """
    matchups = [
        ("seq vs adv",    SequenceBotStrategy(), AdvancedBotStrategy(), 17),
        ("elite vs adv",  EliteBotStrategy(),    AdvancedBotStrategy(), 23),
        ("elite vs elite",EliteBotStrategy(),    EliteBotStrategy(),    31),
    ]

    all_X: list[list[float]] = []
    all_y: list[float] = []
    t0 = time.perf_counter()

    for desc, sa, sb, seed in matchups:
        print(f"  {desc}: {n_per_matchup} games …", end=" ", flush=True)
        t1  = time.perf_counter()
        X, y = _run_matchup_games(sa, sb, n_per_matchup, seed)
        all_X.extend(X)
        all_y.extend(y)
        print(f"{len(X):,} samples  ({time.perf_counter()-t1:.1f}s)", flush=True)

    return np.array(all_X, dtype=np.float32), np.array(all_y, dtype=np.float32)


# ── Serialisation ─────────────────────────────────────────────────────────────

def _export_mlp_classifier(model: MLPClassifier, scaler: StandardScaler) -> dict:
    """Fold StandardScaler into the first weight layer, export as JSON MLP.

    Output activation is sigmoid (MLPClassifier default for binary),
    so inference returns P(win) in (0, 1).
    """
    coefs      = model.coefs_
    intercepts = model.intercepts_
    mean_       = scaler.mean_
    scale_      = scaler.scale_

    # Fold scaler into first layer
    W0         = coefs[0]                            # (n_features, h1)
    b0         = intercepts[0]                       # (h1,)
    W0_scaled  = W0 / scale_[:, np.newaxis]
    b0_scaled  = b0 - (mean_ / scale_) @ W0

    layers = []
    for i, (W, b) in enumerate(zip(coefs, intercepts)):
        W_use = W0_scaled if i == 0 else W
        b_use = b0_scaled if i == 0 else b
        layers.append({"W": W_use.T.tolist(), "b": b_use.tolist()})

    # Activation sequence: relu…relu…sigmoid (MLPClassifier with logistic output)
    return {"type": "mlp_classifier", "layers": layers}


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=DEFAULT_GAMES_PER_MATCHUP,
                        help="games per matchup (3 matchups total)")
    args = parser.parse_args()

    CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_train_cache.npz")

    print("=== Canasta Value Function Training v3 (elite-data, 128-64 net) ===")
    if os.path.exists(CACHE):
        print(f"Loading cached dataset from {CACHE} …")
        data = np.load(CACHE)
        X, y = data["X"], data["y"]
    else:
        print(f"Generating {3 * args.games} games across 3 diverse matchups …")
        X, y = _generate_data(args.games)
        np.savez_compressed(CACHE, X=X, y=y)
        print(f"Dataset cached to {CACHE}")
    print(f"\nDataset: {X.shape[0]:,} samples  |  "
          f"win rate: {y.mean():.3f}  (want ~0.5)")

    print("\nTraining MLPClassifier (128-64 hidden, sigmoid output) …")
    # Skip cross-validation (expensive on 400k+ samples) — train on full data.
    # For quick quality estimate: hold out last 10% as a validation split.
    split = int(0.9 * len(X))
    X_tr, X_val = X[:split], X[split:]
    y_lbl = (y > 0.5).astype(int)
    y_tr,  y_val = y_lbl[:split], y_lbl[split:]

    scaler = StandardScaler()
    X_tr_sc  = scaler.fit_transform(X_tr)
    X_val_sc = scaler.transform(X_val)

    clf = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation="relu",
        solver="adam",
        learning_rate_init=2e-4,
        batch_size=512,          # larger batches → fewer updates per epoch → faster
        max_iter=300,
        random_state=0,
        early_stopping=True,
        n_iter_no_change=20,
        validation_fraction=0.1,
    )
    clf.fit(X_tr_sc, y_tr)

    # Quick holdout metrics (vectorised — do NOT iterate sample-by-sample)
    from sklearn.metrics import roc_auc_score, accuracy_score
    y_pred_p = clf.predict_proba(X_val_sc)[:, 1]
    auc = roc_auc_score(y_val, y_pred_p)
    acc = accuracy_score(y_val, (y_pred_p > 0.5).astype(int))
    print(f"Holdout AUC: {auc:.4f}  |  Acc: {acc:.4f}  (n={len(y_val):,})")

    # Retrain on full data with same hyperparams
    scaler2 = StandardScaler()
    X_sc    = scaler2.fit_transform(X)
    clf2    = MLPClassifier(
        hidden_layer_sizes=(128, 64),
        activation="relu",
        solver="adam",
        learning_rate_init=2e-4,
        batch_size=512,
        max_iter=300,
        random_state=0,
        early_stopping=True,
        n_iter_no_change=20,
        validation_fraction=0.1,
    )
    clf2.fit(X_sc, y_lbl)
    clf, scaler = clf2, scaler2

    payload = _export_mlp_classifier(clf, scaler)
    os.makedirs(os.path.dirname(WEIGHTS_PATH), exist_ok=True)
    with open(WEIGHTS_PATH, "w") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = os.path.getsize(WEIGHTS_PATH) / 1024
    print(f"\nWeights saved -> {WEIGHTS_PATH}  ({size_kb:.1f} KB)")
    print("Done.")


if __name__ == "__main__":
    main()
