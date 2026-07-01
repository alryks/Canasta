"""SQLAlchemy models (plan section 10/12): games, players, deals, chat_messages.

Mirrors the persistent side of the schema in engine/models.py section 9 --
these tables only exist to survive a server restart / outlive a game (NFR-8),
the live game state lives in Redis while a deal is in progress (section 10).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)

    target_score: Mapped[int] = mapped_column(default=5000)
    discard_visibility: Mapped[str] = mapped_column(String(16), default="TOP_ONLY")
    status: Mapped[str] = mapped_column(String(16), default="LOBBY")
    current_deal_number: Mapped[int] = mapped_column(default=0)
    winner_team_id: Mapped[str | None] = mapped_column(String(8), default=None)

    players: Mapped[list["Player"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    deals: Mapped[list["Deal"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    name: Mapped[str] = mapped_column(String(64))
    seat: Mapped[int | None] = mapped_column(default=None)
    team_id: Mapped[str | None] = mapped_column(String(8), default=None)
    session_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_host: Mapped[bool] = mapped_column(default=False)
    connected: Mapped[bool] = mapped_column(default=True)

    game: Mapped[Game] = relationship(back_populates="players")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    deal_number: Mapped[int]
    score_breakdown: Mapped[dict] = mapped_column(JSON)
    team_scores_after: Mapped[dict] = mapped_column(JSON)

    game: Mapped[Game] = relationship(back_populates="deals")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    game_id: Mapped[str] = mapped_column(ForeignKey("games.id"))
    player_id: Mapped[str | None] = mapped_column(
        ForeignKey("players.id"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    text: Mapped[str] = mapped_column(String(2000))

    game: Mapped[Game] = relationship(back_populates="chat_messages")
