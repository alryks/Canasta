import contextlib

from fastapi.testclient import TestClient


def _create_game(client: TestClient) -> dict:
    response = client.post(
        "/games",
        json={"host_name": "Alice", "target_score": 5000, "discard_visibility": "TOP_ONLY"},
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
