import pytest

from app.engine.models import opening_threshold


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, 30),
        (500, 30),
        (999, 30),
        (1000, 60),
        (1999, 60),
        (2000, 90),
        (2999, 90),
        (3000, 120),
        (3999, 120),
        (4000, 150),
        (10000, 150),
    ],
)
def test_opening_threshold(score: int, expected: int) -> None:
    assert opening_threshold(score) == expected
