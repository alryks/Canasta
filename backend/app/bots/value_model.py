"""
Canasta learned positional value function — pure-Python MLP inference.

v2 changes:
  - Supports both regression (type=mlp) and classification (type=mlp_classifier)
  - Classifier output: P(our team wins deal), converted to EV scale at inference
  - predict_value returns (P - 0.5) * SCORE_SCALE so sign/magnitude match heuristic
"""
from __future__ import annotations

import json
import math
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.engine import DealState

WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "value_weights.json")
N_FEATURES = 36
# Scale for converting P(win) → heuristic-compatible EV:
#   P=1.0 → +7000, P=0.5 → 0, P=0.0 → -7000
SCORE_SCALE = 14_000.0


# ── Feature extraction ────────────────────────────────────────────────────────

def extract_features(deal: "DealState", player_id: str) -> list[float]:
    """Return a 34-float feature vector for the current position.

    Always relative to player_id's team vs opponent so symmetry is preserved.
    Roughly [0,1]-normalised; a few can slightly exceed 1 for extreme states.
    Layout: 14 per-team features × 2 teams + 6 global = 34 total.
    """
    my_team_id = deal.player_team[player_id]
    opp_team_id = next(t for t in deal.teams if t != my_team_id)

    def _team_feats(team_id: str) -> list[float]:
        table = deal.teams[team_id]
        hand_cards: list = []
        for pid, cards in deal.hands.items():
            if deal.player_team[pid] == team_id:
                hand_cards.extend(cards)

        playable = [c for c in hand_cards if not c.is_three]
        wilds     = [c for c in playable if c.is_wild]
        naturals  = [c for c in playable if not c.is_wild]

        rank_cnt: dict = {}
        for c in naturals:
            rank_cnt[c.rank] = rank_cnt.get(c.rank, 0) + 1

        pairs   = sum(1 for v in rank_cnt.values() if v >= 2)
        triples = sum(1 for v in rank_cnt.values() if v >= 3)

        closed_melds = [m for m in table.melds if m.is_closed]
        open_melds   = [m for m in table.melds if not m.is_closed]
        largest_open = max((m.size for m in open_melds), default=0)
        meld_pts     = sum(m.point_value for m in table.melds)
        canasta_bon  = sum(m.canasta_bonus for m in table.melds)
        penalty      = abs(deal.penalties.get(team_id, 0))

        # Going-out potential: has canasta AND very few cards left?
        going_out_now = float(bool(closed_melds) and len(playable) <= 3)

        # Nearest open meld to completing a canasta (0 = nothing open)
        nearest_to_canasta = max((m.size / 7.0 for m in open_melds), default=0.0)

        return [
            min(len(closed_melds), 7) / 7.0,           # closed-canasta count
            min(len(open_melds),   6) / 6.0,            # open-meld count
            min(meld_pts,    2000) / 2000.0,             # meld table points
            min(canasta_bon, 7000) / 7000.0,             # canasta bonuses locked in
            min(len(playable),  26) / 26.0,              # combined playable hand size
            min(len(wilds),      8) /  8.0,              # wilds in hand
            min(pairs,          11) / 11.0,              # pairs in hand
            min(triples,         6) /  6.0,              # triples in hand
            min(sum(c.point_value for c in playable), 600) / 600.0,  # hand value
            float(table.is_opened),                      # team has opened (0/1)
            min(penalty, 3000) / 3000.0,                # accumulated -1000 penalties
            largest_open / 7.0,                          # progress of biggest open meld
            going_out_now,                               # can go out this/next turn?
            nearest_to_canasta,                          # closest open meld to canasta
        ]   # 14 features per team

    my_f  = _team_feats(my_team_id)
    opp_f = _team_feats(opp_team_id)

    my_thresh  = deal.thresholds.get(my_team_id,  30)
    opp_thresh = deal.thresholds.get(opp_team_id, 30)
    my_pen  = abs(deal.penalties.get(my_team_id,  0)) / 1000.0
    opp_pen = abs(deal.penalties.get(opp_team_id, 0)) / 1000.0

    # Pile frozen: top card is wild → opponents need a natural pair to take it.
    frozen_pile = float(
        bool(deal.discard_pile) and deal.discard_pile[-1].is_wild
    )

    global_f = [
        min(len(deal.discard_pile), 60) / 60.0,    # pile size
        len(deal.deck) / 108.0,                     # deck remaining (0 = exhausted)
        1.0 - len(deal.deck) / 108.0,               # game progress (0 = start)
        (my_thresh - opp_thresh) / 120.0,           # threshold diff (>0 = we're behind)
        opp_pen - my_pen,                            # relative penalty advantage
        frozen_pile,                                 # pile frozen by wild (0/1)
        my_thresh / 150.0,                           # our match-score tier (30→150 mapped 0→1)
        opp_thresh / 150.0,                          # opp match-score tier
    ]   # 8 features → 14 + 14 + 8 = 36 total

    return my_f + opp_f + global_f   # 14 + 14 + 8 = 36 total


# ── Inference models ──────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


class _MLPInference:
    """Pure-Python 2-hidden-layer MLP.

    type = 'mlp'            → ReLU hidden + linear output (regression)
    type = 'mlp_classifier' → ReLU hidden + sigmoid output (P(win) in (0,1))
    """

    def __init__(self, data: dict) -> None:
        self.layers: list[dict] = data["layers"]
        self.is_classifier: bool = (data.get("type") == "mlp_classifier")

    def predict(self, x: list[float]) -> float:
        for i, layer in enumerate(self.layers):
            W, b = layer["W"], layer["b"]
            is_last = (i == len(self.layers) - 1)
            x_new = []
            for row, bias in zip(W, b):
                val = sum(xi * wi for xi, wi in zip(x, row)) + bias
                if is_last:
                    val = _sigmoid(val) if self.is_classifier else val
                else:
                    val = val if val > 0.0 else 0.0   # ReLU
                x_new.append(val)
            x = x_new
        return x[0]


class _LinearInference:
    """Ridge regression: y = X · coef + intercept"""

    def __init__(self, data: dict) -> None:
        self.coef      = data["coef"]
        self.intercept = data["intercept"]

    def predict(self, x: list[float]) -> float:
        return sum(xi * wi for xi, wi in zip(x, self.coef)) + self.intercept


_model: "_MLPInference | _LinearInference | None" = None
_is_classifier: bool = False


def load_model() -> bool:
    """Load weights from value_weights.json. Returns True if successful."""
    global _model, _is_classifier
    if not os.path.exists(WEIGHTS_PATH):
        return False
    try:
        with open(WEIGHTS_PATH) as f:
            data = json.load(f)
        mtype = data.get("type", "")
        if mtype in ("mlp", "mlp_classifier"):
            _model = _MLPInference(data)
            _is_classifier = (mtype == "mlp_classifier")
        elif mtype == "linear":
            _model = _LinearInference(data)
            _is_classifier = False
        else:
            return False
        return True
    except Exception:
        return False


def predict_value(deal: "DealState", player_id: str) -> float | None:
    """Predict positional value in heuristic-compatible EV units.

    Regression model: returns raw prediction × SCORE_SCALE.
    Classifier model: returns (P(win) − 0.5) × SCORE_SCALE
                      → +7000 when certain we win, −7000 when certain we lose.
    Returns None if model not loaded.
    """
    if _model is None:
        return None
    try:
        features = extract_features(deal, player_id)
        raw = _model.predict(features)
        if _is_classifier:
            return (raw - 0.5) * SCORE_SCALE
        return raw * SCORE_SCALE
    except Exception:
        return None
