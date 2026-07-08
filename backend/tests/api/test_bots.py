"""Bots (plan follow-up): host fills empty seats with a simple bot so a game
can be started and played without needing 4 humans. `SimpleBotStrategy`
always draws from the deck and discards the first card in hand; these tests
drive the full WS protocol and never send an intent on a bot's behalf --
the bot's own moves must show up purely from `bot_runner` reacting to state
changes (see app/ws/bot_runner.py).
"""

from __future__ import annotations

import contextlib

import pytest
from fastapi.testclient import TestClient

from app.redis_store import RedisGameStore
from app.ws import bot_runner, router
from tests.api.conftest import create_game, join_game


async def _noop(*args: object, **kwargs: object) -> None:
    return None


def test_add_bot_seats_a_bot_with_the_right_team(client: TestClient) -> None:
    game = create_game(client)
    game_id = game["game_id"]

    with client.websocket_connect(
        f"/ws/games/{game_id}?token={game['host_session_token']}"
    ) as host_ws:
        host_ws.receive_json()  # initial lobby_state

        host_ws.send_json({"type": "add_bot", "data": {"seat": 1}})
        state = host_ws.receive_json()

    assert state["type"] == "lobby_state"
    [bot] = [p for p in state["data"]["players"] if p["id"] != game["player_id"]]
    assert bot["is_bot"] is True
    assert bot["seat"] == 1
    assert bot["team_id"] == "B"
    assert bot["connected"] is True


def test_add_bot_rejected_for_non_host(client: TestClient) -> None:
    game = create_game(client)
    game_id = game["game_id"]
    bob = join_game(client, game_id, "Bob")

    with client.websocket_connect(
        f"/ws/games/{game_id}?token={bob['session_token']}"
    ) as bob_ws:
        bob_ws.receive_json()
        bob_ws.send_json({"type": "add_bot", "data": {"seat": 1}})
        error = bob_ws.receive_json()
        assert error["type"] == "action_error"


def test_add_bot_rejected_for_taken_seat(client: TestClient) -> None:
    game = create_game(client)
    game_id = game["game_id"]

    with client.websocket_connect(
        f"/ws/games/{game_id}?token={game['host_session_token']}"
    ) as host_ws:
        host_ws.receive_json()
        host_ws.send_json({"type": "add_bot", "data": {"seat": 0}})
        host_ws.receive_json()

        host_ws.send_json({"type": "add_bot", "data": {"seat": 0}})
        error = host_ws.receive_json()
        assert error["type"] == "action_error"


def _connect_and_start(
    client: TestClient, redis_store: RedisGameStore, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict, dict]:
    """Host (seat 0) + Bob (seat 2) are real players; bots sit at 1 and 3 --
    so the turn order (seat 0->1->2->3) hands off to a bot immediately after
    the host's first discard."""
    # the very first deal's opener is randomized in production; pin it to
    # the host so this test's fixed seat-rotation narrative holds
    monkeypatch.setattr(
        router, "_pick_first_player", lambda player_order: player_order[0]
    )

    game = create_game(client)
    game_id = game["game_id"]
    host_id = game["player_id"]
    bob = join_game(client, game_id, "Bob")
    bob_id = bob["player_id"]

    with contextlib.ExitStack() as stack:
        host_ws = stack.enter_context(
            client.websocket_connect(
                f"/ws/games/{game_id}?token={game['host_session_token']}"
            )
        )
        host_ws.receive_json()
        bob_ws = stack.enter_context(
            client.websocket_connect(
                f"/ws/games/{game_id}?token={bob['session_token']}"
            )
        )
        host_ws.receive_json()
        bob_ws.receive_json()

        sockets = {host_id: host_ws, bob_id: bob_ws}

        def _send_and_drain(sender_id: str, message: dict) -> dict:
            sockets[sender_id].send_json(message)
            states = {pid: s.receive_json() for pid, s in sockets.items()}
            return states[sender_id]

        _send_and_drain(
            host_id, {"type": "assign_seat", "data": {"player_id": host_id, "seat": 0}}
        )
        _send_and_drain(
            host_id, {"type": "assign_seat", "data": {"player_id": bob_id, "seat": 2}}
        )
        _send_and_drain(host_id, {"type": "add_bot", "data": {"seat": 1}})
        _send_and_drain(host_id, {"type": "add_bot", "data": {"seat": 3}})

        start_state = _send_and_drain(host_id, {"type": "start_game", "data": {}})
        assert start_state["data"]["turn_player_id"] == host_id

        # both teams pre-opened -- this test is about the bot chaining
        # through its turn, not about threshold/meld mechanics
        game_state = redis_store.get_state(game_id)
        game_state.current_deal.teams["A"].is_opened = True
        game_state.current_deal.teams["B"].is_opened = True
        redis_store.set_state(game_id, game_state)

        hand = start_state["data"]["hands"][host_id]
        _send_and_drain(host_id, {"type": "draw_deck", "data": {}})
        after_discard = _send_and_drain(
            host_id, {"type": "discard", "data": {"card_id": hand[0]["id"]}}
        )
        bot_seat1_id = after_discard["data"]["turn_player_id"]
        assert bot_seat1_id not in (host_id, bob_id)

        # nothing sent for the bot from here -- just drain the broadcasts of
        # its own moves (draw, any melds, discard) until the turn hands off
        after_bot_draw = {pid: s.receive_json() for pid, s in sockets.items()}
        assert after_bot_draw[host_id]["data"]["turn_player_id"] == bot_seat1_id
        assert after_bot_draw[host_id]["data"]["turn_phase"] == "ACT"

        for _ in range(30):
            states = {pid: s.receive_json() for pid, s in sockets.items()}
            if states[host_id]["data"]["turn_player_id"] != bot_seat1_id:
                break
        else:
            raise AssertionError("bot never finished its turn")
        return states, {
            "host_id": host_id,
            "bob_id": bob_id,
            "bot_seat1_id": bot_seat1_id,
        }


def test_bot_auto_plays_its_turn_without_any_bot_intent(
    client: TestClient, redis_store: RedisGameStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bot_runner, "BOT_MOVE_DELAY_RANGE_SECONDS", (0.01, 0.01))

    after_bot_turn, ids = _connect_and_start(client, redis_store, monkeypatch)

    assert after_bot_turn[ids["host_id"]]["data"]["turn_player_id"] == ids["bob_id"]
    assert after_bot_turn[ids["host_id"]]["data"]["turn_phase"] == "DRAW"


def test_host_can_force_skip_a_stuck_bot_without_a_timeout(
    client: TestClient, redis_store: RedisGameStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate a wedged bot (e.g. a strategy bug) by disabling auto-play
    # entirely once the turn reaches it -- the host must still be able to
    # force the game forward.
    monkeypatch.setattr(bot_runner, "maybe_schedule_bot_turn", _noop)
    # the very first deal's opener is randomized in production; pin it to
    # the host so the host's own draw+discard below reliably hands the turn
    # to a bot next
    monkeypatch.setattr(
        router, "_pick_first_player", lambda player_order: player_order[0]
    )

    game = create_game(client)
    game_id = game["game_id"]
    host_id = game["player_id"]

    with client.websocket_connect(
        f"/ws/games/{game_id}?token={game['host_session_token']}"
    ) as host_ws:
        host_ws.receive_json()
        host_ws.send_json(
            {"type": "assign_seat", "data": {"player_id": host_id, "seat": 0}}
        )
        host_ws.receive_json()
        host_ws.send_json({"type": "add_bot", "data": {"seat": 1}})
        host_ws.receive_json()
        host_ws.send_json({"type": "add_bot", "data": {"seat": 2}})
        host_ws.receive_json()
        host_ws.send_json({"type": "add_bot", "data": {"seat": 3}})
        host_ws.receive_json()

        host_ws.send_json({"type": "start_game", "data": {}})
        start_state = host_ws.receive_json()

        game_state = redis_store.get_state(game_id)
        game_state.current_deal.teams["A"].is_opened = True
        game_state.current_deal.teams["B"].is_opened = True
        redis_store.set_state(game_id, game_state)

        hand = start_state["data"]["hands"][host_id]
        host_ws.send_json({"type": "draw_deck", "data": {}})
        host_ws.receive_json()
        host_ws.send_json({"type": "discard", "data": {"card_id": hand[0]["id"]}})
        stuck_state = host_ws.receive_json()
        stuck_bot_id = stuck_state["data"]["turn_player_id"]
        assert stuck_bot_id != host_id

        # no timer was ever armed (bots are always "connected") and
        # maybe_schedule_bot_turn is disabled -- host can still force it
        host_ws.send_json({"type": "skip_turn_with_penalty", "data": {}})
        skipped_state = host_ws.receive_json()

    assert skipped_state["type"] == "game_state"
    assert skipped_state["data"]["turn_player_id"] not in (host_id, stuck_bot_id)

    game_state = redis_store.get_state(game_id)
    stuck_team_id = game_state.current_deal.player_team[stuck_bot_id]
    assert game_state.current_deal.penalties[stuck_team_id] == -1000
