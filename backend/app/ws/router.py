"""WS handler: connect by session_token, broadcast lobby_state (plan section 8,
step 13). Game-start intent handling (assign_seat, start_game, ...) lands in
the next step.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.models import Game, Player
from app.db.session import async_session
from app.ws.manager import manager
from app.ws.serialization import build_lobby_state

router = APIRouter()


def _player_public(player: Player) -> dict:
    return {
        "id": player.id,
        "name": player.name,
        "seat": player.seat,
        "team_id": player.team_id,
        "connected": player.connected,
        "is_host": player.is_host,
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
        await manager.broadcast(game_id, await _lobby_state_message(session, game))

    try:
        while True:
            await websocket.receive_json()
    except WebSocketDisconnect:
        async with async_session() as session:
            disconnected = await session.get(Player, player.id)
            if disconnected is not None:
                disconnected.connected = False
                game = await session.get(Game, game_id)
                await session.commit()
                if game is not None:
                    await manager.broadcast(
                        game_id, await _lobby_state_message(session, game)
                    )
        manager.unregister(game_id, player.id)
