"""WS handler: connect by session_token, dispatch lobby intents (plan section 8,
phase 3 scope only -- draw/meld/discard intents land in phase 4).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.models import Game, Player
from app.db.session import async_session
from app.engine.engine import GameSettings, GameState, PlayerInfo, start_new_deal
from app.engine.errors import IllegalActionError
from app.redis_store import RedisGameStore
from app.ws.game_intents import GAME_INTENTS, apply_game_intent
from app.ws.manager import manager
from app.ws.serialization import build_client_game_state, build_lobby_state

router = APIRouter()

store = RedisGameStore()

SEATS = (0, 1, 2, 3)


class LobbyActionError(Exception):
    pass


def _team_for_seat(seat: int) -> str:
    return "A" if seat % 2 == 0 else "B"


def _player_public(player: Player) -> dict:
    return {
        "id": player.id,
        "name": player.name,
        "seat": player.seat,
        "team_id": player.team_id,
        "connected": player.connected,
        "is_host": player.is_host,
    }


def _player_connection_message(player_id: str, connected: bool) -> dict:
    return {
        "type": "player_connection",
        "data": {"player_id": player_id, "connected": connected},
    }


async def _lobby_state_message(session, game: Game) -> dict:
    players = (
        await session.scalars(select(Player).where(Player.game_id == game.id))
    ).all()
    host = next((p for p in players if p.is_host), None)
    return build_lobby_state(
        players=[_player_public(p) for p in players],
        target_score=game.target_score,
        discard_visibility=game.discard_visibility,
        host_id=host.id if host else "",
    )


def _build_initial_game_state(game: Game, players: list[Player]) -> GameState:
    seated = sorted(players, key=lambda p: p.seat)
    player_order = [p.id for p in seated]
    player_team = {p.id: p.team_id for p in seated}
    scores = {"A": 0, "B": 0}
    deal = start_new_deal(player_order, player_team, scores)

    return GameState(
        game_id=game.id,
        settings=GameSettings(
            target_score=game.target_score,
            discard_visibility=game.discard_visibility,
        ),
        players=[
            PlayerInfo(
                id=p.id,
                name=p.name,
                session_token=p.session_token,
                seat=p.seat,
                team_id=p.team_id,
                connected=p.connected,
            )
            for p in seated
        ],
        scores=scores,
        current_deal=deal,
    )


async def _handle_assign_seat(session, game: Game, sender: Player, data: dict) -> None:
    if not sender.is_host:
        raise LobbyActionError("only the host can assign seats")
    if game.status != "LOBBY":
        raise LobbyActionError("game already started")

    seat = data.get("seat")
    player_id = data.get("player_id")
    if seat not in SEATS:
        raise LobbyActionError(f"invalid seat {seat!r}")

    target = await session.get(Player, player_id)
    if target is None or target.game_id != game.id:
        raise LobbyActionError(f"no such player {player_id!r}")

    others = (
        await session.scalars(
            select(Player).where(Player.game_id == game.id, Player.seat == seat)
        )
    ).all()
    if any(p.id != target.id for p in others):
        raise LobbyActionError(f"seat {seat} is already taken")

    target.seat = seat
    target.team_id = _team_for_seat(seat)
    await session.commit()
    await manager.broadcast(game.id, await _lobby_state_message(session, game))


async def _handle_set_lobby_settings(
    session, game: Game, sender: Player, data: dict
) -> None:
    if not sender.is_host:
        raise LobbyActionError("only the host can change lobby settings")
    if game.status != "LOBBY":
        raise LobbyActionError("game already started")

    if "target_score" in data:
        game.target_score = int(data["target_score"])
    if "discard_visibility" in data:
        game.discard_visibility = data["discard_visibility"]
    await session.commit()
    await manager.broadcast(game.id, await _lobby_state_message(session, game))


async def _handle_start_game(session, game: Game, sender: Player) -> None:
    if not sender.is_host:
        raise LobbyActionError("only the host can start the game")
    if game.status != "LOBBY":
        raise LobbyActionError("game already started")

    players = (
        await session.scalars(select(Player).where(Player.game_id == game.id))
    ).all()
    seats_taken = {p.seat for p in players}
    if len(players) != 4 or seats_taken != set(SEATS):
        raise LobbyActionError("all 4 seats must be filled before starting")

    game_state = _build_initial_game_state(game, list(players))
    store.set_state(game.id, game_state)

    game.status = "IN_PROGRESS"
    game.current_deal_number = 1
    await session.commit()

    await manager.broadcast_personalized(
        game.id, lambda pid: build_client_game_state(game_state, pid)
    )


async def _handle_game_intent(
    session, game: Game, sender_id: str, intent: str, data: dict
) -> None:
    result = await apply_game_intent(store, session, game, sender_id, intent, data)

    if not result.deal_completed:
        await manager.broadcast_personalized(
            game.id, lambda pid: build_client_game_state(result.game_state, pid)
        )
        return

    await manager.broadcast(game.id, result.deal_result_message)
    if result.winner_team_id is not None:
        await manager.broadcast(
            game.id,
            {"type": "game_over", "data": {"winner_team": result.winner_team_id}},
        )
    else:
        await manager.broadcast_personalized(
            game.id, lambda pid: build_client_game_state(result.game_state, pid)
        )


async def _handle_intent(game_id: str, sender_id: str, message: dict) -> None:
    intent = message.get("type")
    data = message.get("data", {})

    async with async_session() as session:
        game = await session.get(Game, game_id)
        sender = await session.get(Player, sender_id)
        if game is None or sender is None:
            return

        try:
            if intent == "assign_seat":
                await _handle_assign_seat(session, game, sender, data)
            elif intent == "set_lobby_settings":
                await _handle_set_lobby_settings(session, game, sender, data)
            elif intent == "start_game":
                await _handle_start_game(session, game, sender)
            elif intent in GAME_INTENTS:
                await _handle_game_intent(session, game, sender_id, intent, data)
            else:
                raise LobbyActionError(f"unknown intent {intent!r}")
        except (LobbyActionError, IllegalActionError) as exc:
            await manager.send_to(
                game_id,
                sender_id,
                {"type": "action_error", "data": {"reason": str(exc)}},
            )


@router.websocket("/ws/games/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str, token: str) -> None:
    async with async_session() as session:
        game = await session.get(Game, game_id)
        player = None
        if game is not None:
            player = (
                await session.scalars(
                    select(Player).where(
                        Player.game_id == game_id, Player.session_token == token
                    )
                )
            ).first()

        if game is None or player is None:
            await websocket.close(code=4001)
            return

        await websocket.accept()
        player.connected = True
        await session.commit()
        manager.register(game_id, player.id, websocket)

        if game.status == "LOBBY":
            await manager.broadcast(game_id, await _lobby_state_message(session, game))
        else:
            # FR-36: reconnect snapshot is just the same full GameState the
            # Redis store already holds -- it carries turn_state.phase, so
            # the player lands back on exactly the phase they left on.
            await manager.broadcast(
                game_id, _player_connection_message(player.id, True)
            )
            game_state = store.get_state(game_id)
            if game_state is not None:
                await websocket.send_json(
                    build_client_game_state(game_state, player.id)
                )

    try:
        while True:
            message = await websocket.receive_json()
            await _handle_intent(game_id, player.id, message)
    except WebSocketDisconnect:
        # Unregister before broadcasting -- the disconnecting player's own
        # socket is already closed at the transport level, so sending to it
        # would raise.
        manager.unregister(game_id, player.id)
        async with async_session() as session:
            disconnected = await session.get(Player, player.id)
            if disconnected is not None:
                disconnected.connected = False
                game = await session.get(Game, game_id)
                await session.commit()
                if game is not None and game.status == "LOBBY":
                    await manager.broadcast(
                        game_id, await _lobby_state_message(session, game)
                    )
                elif game is not None and game.status == "IN_PROGRESS":
                    await manager.broadcast(
                        game_id, _player_connection_message(player.id, False)
                    )
