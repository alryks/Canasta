"""add is_bot to players

Revision ID: b60561ad254e
Revises: bbe13bab39f2
Create Date: 2026-07-02 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b60561ad254e"
down_revision: Union[str, Sequence[str], None] = "bbe13bab39f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "players",
        sa.Column(
            "is_bot", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    # server_default was only needed to backfill existing rows -- afterwards
    # the ORM's Python-side default is the single source of truth, matching
    # every other boolean column on this table (is_host, connected).
    op.alter_column("players", "is_bot", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("players", "is_bot")
