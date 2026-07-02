"""API-layer test fixtures: an in-memory SQLite DB standing in for Postgres.

The tables are simple (no Postgres-specific types), so SQLite is a faithful
enough stand-in and lets these tests run without Docker/Postgres at all --
the schema itself is already verified against real Postgres via Alembic.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
import redis
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.ws.bot_runner as bot_runner
import app.ws.router as ws_router
from app.db.models import Base
from app.db.session import get_db
from app.main import app
from app.redis_store import RedisGameStore


@pytest_asyncio.fixture
async def db_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    yield session_factory
    await engine.dispose()


@pytest.fixture
def client(
    db_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[TestClient]:
    async def _get_db_override() -> AsyncIterator[AsyncSession]:
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db_override
    # The WS router talks to the DB directly (no FastAPI Depends plumbing for
    # websockets), so it needs its own session factory swapped in for tests.
    monkeypatch.setattr(ws_router, "async_session", db_session_factory)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def redis_store(monkeypatch: pytest.MonkeyPatch) -> RedisGameStore:
    test_client = redis.Redis(host="127.0.0.1", port=6379, db=15, decode_responses=True)
    try:
        test_client.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip(
            "Redis is not reachable at 127.0.0.1:6379 (run `docker compose up -d redis`)"
        )
    test_client.flushdb()
    store = RedisGameStore(client=test_client)
    monkeypatch.setattr(ws_router, "store", store)
    monkeypatch.setattr(bot_runner, "store", store)
    return store
