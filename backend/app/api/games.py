"""Lobby REST endpoints (plan section 11): everything before the WS socket opens."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Game, Player
from app.db.session import get_db
from app.schemas import (
    CreateGameRequest,
    CreateGameResponse,
    JoinGameRequest,
    JoinGameResponse,
    LobbyStateResponse,
    PlayerPublic,
)

router = APIRouter(prefix="/games", tags=["lobby"])

MAX_PLAYERS = 4


def _generate_session_token() -> str:
    return secrets.token_urlsafe(24)


async def _get_game_or_404(game_id: str, db: AsyncSession) -> Game:
    game = await db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    return game


async def _get_players(db: AsyncSession, game_id: str) -> list[Player]:
    result = await db.scalars(select(Player).where(Player.game_id == game_id))
    return list(result.all())


@router.post("", response_model=CreateGameResponse)
async def create_game(
    body: CreateGameRequest, db: AsyncSession = Depends(get_db)
) -> CreateGameResponse:
    game = Game(
        target_score=body.target_score, discard_visibility=body.discard_visibility
    )
    db.add(game)
    await db.flush()

    host = Player(
        game_id=game.id,
        name=body.host_name,
        session_token=_generate_session_token(),
        is_host=True,
    )
    db.add(host)
    await db.commit()

    return CreateGameResponse(
        game_id=game.id,
        invite_link=f"/join/{game.id}",
        host_session_token=host.session_token,
        player_id=host.id,
    )


@router.post("/{game_id}/join", response_model=JoinGameResponse)
async def join_game(
    game_id: str, body: JoinGameRequest, db: AsyncSession = Depends(get_db)
) -> JoinGameResponse:
    game = await _get_game_or_404(game_id, db)
    if game.status != "LOBBY":
        raise HTTPException(status_code=409, detail="game already started")

    players = await _get_players(db, game_id)
    if len(players) >= MAX_PLAYERS:
        raise HTTPException(status_code=409, detail="lobby is full")

    player = Player(
        game_id=game_id, name=body.name, session_token=_generate_session_token()
    )
    db.add(player)
    await db.commit()

    return JoinGameResponse(player_id=player.id, session_token=player.session_token)


@router.get("/{game_id}/lobby", response_model=LobbyStateResponse)
async def get_lobby(
    game_id: str, db: AsyncSession = Depends(get_db)
) -> LobbyStateResponse:
    game = await _get_game_or_404(game_id, db)
    players = await _get_players(db, game_id)
    host = next((p for p in players if p.is_host), None)

    return LobbyStateResponse(
        game_id=game.id,
        status=game.status,
        host_id=host.id if host else "",
        target_score=game.target_score,
        discard_visibility=game.discard_visibility,
        players=[
            PlayerPublic(
                id=p.id,
                name=p.name,
                seat=p.seat,
                team_id=p.team_id,
                connected=p.connected,
                is_host=p.is_host,
            )
            for p in players
        ],
    )
