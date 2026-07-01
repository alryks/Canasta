"""send_chat / chat_message (plan section 8) -- the WS protocol and the
chat_messages table (app/db/models.py) were already specified/created in
earlier phases, but the intent itself was never wired up until now.
"""

from __future__ import annotations


def test_chat_message_broadcasts_to_everyone_including_sender(
    started_game: dict,
) -> None:
    sockets = started_game["sockets"]
    player_ids = started_game["player_ids"]
    sender_id = player_ids[0]

    sockets[sender_id].send_json({"type": "send_chat", "data": {"text": "hi all"}})

    for pid in player_ids:
        message = sockets[pid].receive_json()
        assert message["type"] == "chat_message"
        assert message["data"]["from"] == sender_id
        assert message["data"]["text"] == "hi all"
        assert "ts" in message["data"]


def test_blank_chat_message_is_rejected(started_game: dict) -> None:
    sockets = started_game["sockets"]
    sender_id = started_game["player_ids"][0]

    sockets[sender_id].send_json({"type": "send_chat", "data": {"text": "   "}})

    error = sockets[sender_id].receive_json()
    assert error["type"] == "action_error"
