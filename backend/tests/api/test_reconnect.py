"""Step 19: FR-33/34/36 -- disconnect/reconnect during an active game.

Disconnecting broadcasts a lightweight `player_connection` notice to
everyone else (not a full lobby_state rescan, since there's no lobby left
once IN_PROGRESS). Reconnecting sends the same full `game_state` snapshot
the Redis-backed GameState already holds, so the player lands back on
exactly the turn_state phase they left on -- no separate "resume" logic is
needed, since the whole deal already lives server-side in Redis rather than
in any per-connection memory.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_disconnect_in_act_phase_then_reconnect_gets_identical_snapshot(
    started_game: dict,
) -> None:
    game_id = started_game["game_id"]
    host_id = started_game["host_id"]
    sockets = started_game["sockets"]
    tokens = started_game["tokens"]
    player_ids = started_game["player_ids"]
    test_client: TestClient = started_game["client"]
    turn_player_id = started_game["states"][host_id]["data"]["turn_player_id"]

    # advance the turn player into ACT phase before disconnecting
    sockets[turn_player_id].send_json({"type": "draw_deck", "data": {}})
    states_before = {pid: ws.receive_json() for pid, ws in sockets.items()}
    snapshot_before = states_before[turn_player_id]["data"]

    sockets[turn_player_id].close()

    others = [pid for pid in player_ids if pid != turn_player_id]
    for pid in others:
        notice = sockets[pid].receive_json()
        assert notice["type"] == "player_connection"
        assert notice["data"] == {"player_id": turn_player_id, "connected": False}

    with test_client.websocket_connect(
        f"/ws/games/{game_id}?token={tokens[turn_player_id]}"
    ) as reconnected_ws:
        # the player_connection broadcast goes to everyone still registered,
        # including the reconnecting socket itself
        for pid in [*others, turn_player_id]:
            ws = reconnected_ws if pid == turn_player_id else sockets[pid]
            notice = ws.receive_json()
            assert notice["type"] == "player_connection"
            assert notice["data"] == {"player_id": turn_player_id, "connected": True}

        snapshot_after = reconnected_ws.receive_json()["data"]

        assert snapshot_after["turn_phase"] == snapshot_before["turn_phase"] == "ACT"
        assert snapshot_after["turn_player_id"] == turn_player_id
        assert (
            snapshot_after["hands"][turn_player_id]
            == snapshot_before["hands"][turn_player_id]
        )
        assert snapshot_after["melds"] == snapshot_before["melds"]
        assert snapshot_after["deck_count"] == snapshot_before["deck_count"]


def test_disconnect_not_on_turn_does_not_block_the_active_player(
    started_game: dict,
) -> None:
    host_id = started_game["host_id"]
    sockets = started_game["sockets"]
    player_ids = started_game["player_ids"]
    turn_player_id = started_game["states"][host_id]["data"]["turn_player_id"]
    bystander_id = next(pid for pid in player_ids if pid != turn_player_id)

    sockets[bystander_id].close()

    remaining = [pid for pid in player_ids if pid != bystander_id]
    for pid in remaining:
        notice = sockets[pid].receive_json()
        assert notice["type"] == "player_connection"
        assert notice["data"] == {"player_id": bystander_id, "connected": False}

    sockets[turn_player_id].send_json({"type": "draw_deck", "data": {}})
    for pid in remaining:
        state = sockets[pid].receive_json()
        assert state["type"] == "game_state"
