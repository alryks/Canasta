"""Client-facing WS message builders (plan section 8)."""

from __future__ import annotations


def build_lobby_state(
    *,
    players: list[dict],
    target_score: int,
    discard_visibility: str,
    host_id: str,
) -> dict:
    return {
        "type": "lobby_state",
        "data": {
            "players": players,
            "settings": {
                "target_score": target_score,
                "discard_visibility": discard_visibility,
            },
            "host_id": host_id,
        },
    }
