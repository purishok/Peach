"""Store the final agenda and the original AI suggestion.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("agenda", postgresql.JSONB(), nullable=True))
    op.add_column("meetings", sa.Column("ai_suggestion", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("meetings", "ai_suggestion")
    op.drop_column("meetings", "agenda")
