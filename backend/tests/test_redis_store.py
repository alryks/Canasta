import uuid

import pytest
import redis

from app.engine.engine import DealState, GameSettings, GameState, PlayerInfo
from app.engine.models import Card, MeldKind, Rank, Suit, TeamTable
from app.engine.rules import build_new_meld
from app.engine.turn_fsm import start_turn
from app.redis_store import RedisGameStore


@pytest.fixture
def store() -> RedisGameStore:
    client = redis.Redis(host="127.0.0.1", port=6379, db=15, decode_responses=True)
    try:
        client.ping()
    except redis.exceptions.ConnectionError:
        pytest.skip(
            "Redis is not reachable at 127.0.0.1:6379 (run `docker compose up -d redis`)"
        )
    client.flushdb()
    return RedisGameStore(client=client)


def _sample_game_state() -> GameState:
    wild = Card(id="w1", rank=Rank.TWO, suit=Suit.HEARTS)
    naturals = [
        Card(id="n1", rank=Rank.SEVEN, suit=Suit.SPADES),
        Card(id="n2", rank=Rank.SEVEN, suit=Suit.CLUBS),
    ]
    meld = build_new_meld("m1", "A", [*naturals, wild])

    team_a = TeamTable(team_id="A", melds=[meld], is_opened=True, turn_accumulator=45)
    team_b = TeamTable(team_id="B")

    deal = DealState(
        deck=[Card(id="d1", rank=Rank.KING, suit=Suit.DIAMONDS)],
        discard_pile=[Card(id="disc1", rank=Rank.THREE, suit=Suit.SPADES)],
        teams={"A": team_a, "B": team_b},
        hands={
            "p1": [Card(id="h1", rank=Rank.JOKER, suit=None)],
            "p2": [],
            "p3": [],
            "p4": [],
        },
        thresholds={"A": 30, "B": 30},
        player_order=["p1", "p2", "p3", "p4"],
        player_team={"p1": "A", "p2": "B", "p3": "A", "p4": "B"},
        turn_state=start_turn("p1"),
        penalties={"B": -1000},
    )

    players = [
        PlayerInfo(id="p1", name="Alice", session_token="tok1", seat=0, team_id="A"),
        PlayerInfo(id="p2", name="Bob", session_token="tok2", seat=1, team_id="B"),
        PlayerInfo(id="p3", name="Carol", session_token="tok3", seat=2, team_id="A"),
        PlayerInfo(
            id="p4",
            name="Dave",
            session_token="tok4",
            seat=3,
            team_id="B",
            connected=False,
        ),
    ]

    return GameState(
        game_id=str(uuid.uuid4()),
        settings=GameSettings(target_score=5000, discard_visibility="TOP_ONLY"),
        players=players,
        scores={"A": 1200, "B": 850},
        current_deal=deal,
    )


def test_set_and_get_state_roundtrips_identically(store: RedisGameStore) -> None:
    game_state = _sample_game_state()

    store.set_state(game_state.game_id, game_state)
    loaded = store.get_state(game_state.game_id)

    assert loaded == game_state


def test_get_state_returns_none_when_missing(store: RedisGameStore) -> None:
    assert store.get_state("no-such-game") is None


def test_set_state_overwrites_previous_value(store: RedisGameStore) -> None:
    game_state = _sample_game_state()
    store.set_state(game_state.game_id, game_state)

    game_state.scores["A"] += 500
    store.set_state(game_state.game_id, game_state)

    loaded = store.get_state(game_state.game_id)
    assert loaded is not None
    assert loaded.scores["A"] == game_state.scores["A"]


def test_delete_state(store: RedisGameStore) -> None:
    game_state = _sample_game_state()
    store.set_state(game_state.game_id, game_state)
    store.delete_state(game_state.game_id)
    assert store.get_state(game_state.game_id) is None


def test_lock_is_mutually_exclusive(store: RedisGameStore) -> None:
    game_id = "lock-test-game"
    with store.lock(game_id):
        with pytest.raises(redis.exceptions.LockError):
            with store.lock(game_id, blocking_timeout=0.2):
                pass


def test_lock_releases_after_context_exit(store: RedisGameStore) -> None:
    game_id = "lock-test-game-2"
    with store.lock(game_id):
        pass
    # should not raise / block -- the first lock was released
    with store.lock(game_id):
        pass


def test_meld_kind_survives_roundtrip(store: RedisGameStore) -> None:
    game_state = _sample_game_state()
    store.set_state(game_state.game_id, game_state)
    loaded = store.get_state(game_state.game_id)

    assert loaded is not None
    meld = loaded.current_deal.teams["A"].melds[0]
    assert meld.kind == MeldKind.SET
    assert meld.slots[-1].is_wild
