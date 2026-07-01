from fastapi.testclient import TestClient


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


def test_create_game_returns_host_token_and_invite_link(client: TestClient) -> None:
    body = _create_game(client)
    assert body["game_id"]
    assert body["host_session_token"]
    assert body["player_id"]
    assert body["game_id"] in body["invite_link"]


def test_create_join_join_join_puts_four_players_in_db(client: TestClient) -> None:
    game = _create_game(client)
    game_id = game["game_id"]

    for name in ["Bob", "Carol", "Dave"]:
        response = client.post(f"/games/{game_id}/join", json={"name": name})
        assert response.status_code == 200
        assert response.json()["session_token"]

    lobby = client.get(f"/games/{game_id}/lobby")
    assert lobby.status_code == 200
    data = lobby.json()
    assert len(data["players"]) == 4
    names = {p["name"] for p in data["players"]}
    assert names == {"Alice", "Bob", "Carol", "Dave"}
    assert data["host_id"] == game["player_id"]
    assert data["status"] == "LOBBY"


def test_join_rejects_fifth_player(client: TestClient) -> None:
    game = _create_game(client)
    game_id = game["game_id"]
    for name in ["Bob", "Carol", "Dave"]:
        client.post(f"/games/{game_id}/join", json={"name": name})

    response = client.post(f"/games/{game_id}/join", json={"name": "Eve"})
    assert response.status_code == 409


def test_join_unknown_game_returns_404(client: TestClient) -> None:
    response = client.post("/games/does-not-exist/join", json={"name": "Bob"})
    assert response.status_code == 404
