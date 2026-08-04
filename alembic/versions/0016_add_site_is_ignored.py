"""add is_ignored column to site

Revision ID: 0016_add_site_is_ignored
Revises: 0015_add_reading_site_dt_idx
Create Date: 2026-08-04

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0016_add_site_is_ignored"
down_revision = "0015_add_reading_site_dt_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "site",
        sa.Column("is_ignored", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("site", "is_ignored")
