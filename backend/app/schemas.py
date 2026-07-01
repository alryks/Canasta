"""Pydantic schemas: REST request/response bodies (plan section 11).

WS message payloads (plan section 8) are built as plain dicts in app/ws --
they're server->client only and never need request validation, so a second
schema layer there would just be ceremony.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateGameRequest(BaseModel):
    host_name: str = Field(min_length=1, max_length=64)
    target_score: int = 5000
    discard_visibility: str = "TOP_ONLY"


class CreateGameResponse(BaseModel):
    game_id: str
    invite_link: str
    host_session_token: str
    player_id: str


class JoinGameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class JoinGameResponse(BaseModel):
    player_id: str
    session_token: str


class PlayerPublic(BaseModel):
    id: str
    name: str
    seat: int | None
    team_id: str | None
    connected: bool
    is_host: bool


class LobbyStateResponse(BaseModel):
    game_id: str
    status: str
    host_id: str
    target_score: int
    discard_visibility: str
    players: list[PlayerPublic]
