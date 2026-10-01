"""Restore user identities and item ownership without deleting existing items.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("cognito_sub", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column("items", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True))
    # Older rows have no provable owner. Preserve them under an inaccessible
    # identity: token verification rejects an empty sub. An administrator can
    # later assign these rows after verifying ownership; no first-login takeover.
    op.execute(
        "INSERT INTO users (cognito_sub, name) "
        "SELECT '', 'Unassigned legacy items' WHERE EXISTS (SELECT 1 FROM items)"
    )
    op.execute("UPDATE items SET owner_id = (SELECT id FROM users WHERE cognito_sub = '')")
    op.alter_column("items", "owner_id", nullable=False)
    op.create_foreign_key(
        "fk_items_owner_id_users", "items", "users", ["owner_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_items_owner_id", "items", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_items_owner_id", table_name="items")
    op.drop_constraint("fk_items_owner_id_users", "items", type_="foreignkey")
    op.drop_column("items", "owner_id")
    op.drop_table("users")
