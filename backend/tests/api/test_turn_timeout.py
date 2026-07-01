"""Step 20: FR-35/37 -- turn timeout when the active player disconnects, and
the host's manual "skip with penalty" once that timeout has expired.

The timer duration is a module attribute on `app.ws.turn_timer`, patched down
to a few milliseconds here instead of mocking a clock -- the server side
really does run on a live asyncio event loop under TestClient, so a short
real sleep is simpler and just as deterministic as monkeypatching time.
"""

from __future__ import annotations

from app.redis_store import RedisGameStore
from app.ws import turn_timer


def test_turn_timeout_expires_then_host_skip_penalizes_and_advances(
    started_game: dict, redis_store: RedisGameStore, monkeypatch
) -> None:
    monkeypatch.setattr(turn_timer, "TURN_TIMEOUT_SECONDS", 0.05)

    game_id = started_game["game_id"]
    host_id = started_game["host_id"]
    sockets = started_game["sockets"]
    player_ids = started_game["player_ids"]
    host_ws = sockets[host_id]

    assert started_game["states"][host_id]["data"]["turn_player_id"] == host_id

    # team A already opened, so the plain discard below doesn't need a meld
    # first -- only the turn-passing/timeout mechanics are under test here
    game_state = redis_store.get_state(game_id)
    game_state.current_deal.teams["A"].is_opened = True
    redis_store.set_state(game_id, game_state)

    # pass the turn to a non-host player so the host is free to send the
    # skip command later
    host_ws.send_json({"type": "draw_deck", "data": {}})
    states = {pid: ws.receive_json() for pid, ws in sockets.items()}
    hand = states[host_id]["data"]["hands"][host_id]
    host_ws.send_json({"type": "discard", "data": {"card_id": hand[0]["id"]}})
    states = {pid: ws.receive_json() for pid, ws in sockets.items()}

    stuck_player_id = player_ids[1]
    for state in states.values():
        assert state["data"]["turn_player_id"] == stuck_player_id

    stuck_hand_before = redis_store.get_state(game_id).current_deal.hands[
        stuck_player_id
    ]

    sockets[stuck_player_id].close()

    watchers = [pid for pid in player_ids if pid != stuck_player_id]
    for pid in watchers:
        notice = sockets[pid].receive_json()
        assert notice["type"] == "player_connection"
        assert notice["data"] == {"player_id": stuck_player_id, "connected": False}

    for pid in watchers:
        expired = sockets[pid].receive_json()
        assert expired["type"] == "turn_timer_expired"
        assert expired["data"] == {"player_id": stuck_player_id}

    host_ws.send_json({"type": "skip_turn_with_penalty", "data": {}})
    states = {pid: sockets[pid].receive_json() for pid in watchers}

    next_player_id = player_ids[2]
    for state in states.values():
        assert state["type"] == "game_state"
        assert state["data"]["turn_player_id"] == next_player_id
        assert state["data"]["turn_phase"] == "DRAW"

    game_state = redis_store.get_state(game_id)
    stuck_team_id = game_state.current_deal.player_team[stuck_player_id]
    assert game_state.current_deal.penalties[stuck_team_id] == -1000
    assert game_state.current_deal.hands[stuck_player_id] == stuck_hand_before
    assert not game_state.current_deal.deal_over
    assert turn_timer.expired_player(game_id) is None


def test_skip_with_penalty_rejected_before_timeout_expires(
    started_game: dict, redis_store: RedisGameStore
) -> None:
    game_id = started_game["game_id"]
    host_id = started_game["host_id"]
    sockets = started_game["sockets"]
    host_ws = sockets[host_id]

    host_ws.send_json({"type": "skip_turn_with_penalty", "data": {}})
    error = host_ws.receive_json()
    assert error["type"] == "action_error"

    game_state = redis_store.get_state(game_id)
    assert game_state.current_deal.penalties == {}


def test_skip_with_penalty_rejected_for_non_host(started_game: dict) -> None:
    host_id = started_game["host_id"]
    sockets = started_game["sockets"]
    player_ids = started_game["player_ids"]
    non_host_id = next(pid for pid in player_ids if pid != host_id)

    sockets[non_host_id].send_json({"type": "skip_turn_with_penalty", "data": {}})
    error = sockets[non_host_id].receive_json()
    assert error["type"] == "action_error"
