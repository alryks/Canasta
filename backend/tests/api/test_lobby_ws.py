import contextlib

from fastapi.testclient import TestClient

from app.redis_store import RedisGameStore


def _create_game(client: TestClient) -> dict:
    response = client.post(
        "/games",
        json={
            "host_name": "Alice",
            "target_score": 5000,
            "discard_visibility": "TOP_ONLY",
        },
    )
    assert response.status_code == 200
    return response.json()


def _join(client: TestClient, game_id: str, name: str) -> dict:
    response = client.post(f"/games/{game_id}/join", json={"name": name})
    assert response.status_code == 200
    return response.json()


def test_two_clients_see_each_other_in_lobby_state(client: TestClient) -> None:
    game = _create_game(client)
    game_id = game["game_id"]
    host_token = game["host_session_token"]
    bob = _join(client, game_id, "Bob")

    with client.websocket_connect(f"/ws/games/{game_id}?token={host_token}") as host_ws:
        host_state = host_ws.receive_json()
        assert host_state["type"] == "lobby_state"
        # both rows already exist in the DB (Bob joined via REST before the
        # socket opened) -- lobby_state always reflects the full roster, not
        # just who currently has a live connection
        assert len(host_state["data"]["players"]) == 2

        with client.websocket_connect(
            f"/ws/games/{game_id}?token={bob['session_token']}"
        ) as bob_ws:
            host_state_2 = host_ws.receive_json()
            assert len(host_state_2["data"]["players"]) == 2

            bob_state = bob_ws.receive_json()
            assert len(bob_state["data"]["players"]) == 2
            names = {p["name"] for p in bob_state["data"]["players"]}
            assert names == {"Alice", "Bob"}
            connected = {
                p["name"]: p["connected"] for p in bob_state["data"]["players"]
            }
            assert connected == {"Alice": True, "Bob": True}


def test_connect_with_invalid_token_is_rejected(client: TestClient) -> None:
    game = _create_game(client)
    game_id = game["game_id"]

    with contextlib.suppress(Exception):
        with client.websocket_connect(f"/ws/games/{game_id}?token=not-a-real-token"):
            raise AssertionError("connection should have been rejected")


def test_start_game_flow_sends_personalized_game_state(
    client: TestClient, redis_store: RedisGameStore
) -> None:
    game = _create_game(client)
    game_id = game["game_id"]
    host_id = game["player_id"]
    tokens = {host_id: game["host_session_token"]}

    for name in ["Bob", "Carol", "Dave"]:
        joined = _join(client, game_id, name)
        tokens[joined["player_id"]] = joined["session_token"]

    player_ids = list(tokens.keys())

    with contextlib.ExitStack() as stack:
        sockets: dict[str, object] = {}

        def _connect(pid: str) -> None:
            ws = stack.enter_context(
                client.websocket_connect(f"/ws/games/{game_id}?token={tokens[pid]}")
            )
            sockets[pid] = ws
            ws.receive_json()
            for other_pid, other_ws in sockets.items():
                if other_pid != pid:
                    other_ws.receive_json()

        for pid in player_ids:
            _connect(pid)

        for seat, pid in enumerate(player_ids):
            sockets[host_id].send_json(
                {"type": "assign_seat", "data": {"player_id": pid, "seat": seat}}
            )
            for ws in sockets.values():
                msg = ws.receive_json()
                assert msg["type"] == "lobby_state"

        sockets[host_id].send_json({"type": "start_game", "data": {}})
        states = {pid: ws.receive_json() for pid, ws in sockets.items()}

    for pid, state in states.items():
        assert state["type"] == "game_state"
        data = state["data"]
        own_hand = data["hands"][pid]
        assert isinstance(own_hand, list)
        assert len(own_hand) == 13
        for other_pid, hand in data["hands"].items():
            if other_pid != pid:
                assert hand == 13
        assert data["deck_count"] == 108 - 13 * 4
        assert data["scores"] == {"A": 0, "B": 0}
        assert data["turn_player_id"] == host_id


def test_non_host_cannot_start_game(
    client: TestClient, redis_store: RedisGameStore
) -> None:
    game = _create_game(client)
    game_id = game["game_id"]
    bob = _join(client, game_id, "Bob")

    with client.websocket_connect(
        f"/ws/games/{game_id}?token={bob['session_token']}"
    ) as bob_ws:
        bob_ws.receive_json()  # initial lobby_state
        bob_ws.send_json({"type": "start_game", "data": {}})
        error = bob_ws.receive_json()
        assert error["type"] == "action_error"
