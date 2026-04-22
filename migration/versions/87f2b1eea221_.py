"""empty message

Revision ID: 87f2b1eea221
Revises: 602e0f5dec7c
Create Date: 2026-04-22 21:26:11.029225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87f2b1eea221'
down_revision: Union[str, Sequence[str], None] = '602e0f5dec7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
