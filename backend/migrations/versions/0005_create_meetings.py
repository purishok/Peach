"""Create meetings for weekly reports.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organizer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("participant_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_meetings_title_not_blank"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_meetings_end_after_start"),
        sa.CheckConstraint("participant_count >= 0", name="ck_meetings_participant_count"),
    )
    op.create_index("ix_meetings_starts_at", "meetings", ["starts_at"])
    op.create_index("ix_meetings_organizer_id", "meetings", ["organizer_id"])


def downgrade() -> None:
    op.drop_index("ix_meetings_organizer_id", table_name="meetings")
    op.drop_index("ix_meetings_starts_at", table_name="meetings")
    op.drop_table("meetings")
