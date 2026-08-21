"""add for_reconductoring_age column to reconductoring

Revision ID: 0023_reconductoring_age_flag
Revises: 0022_add_total_rain
Create Date: 2026-08-21

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0023_reconductoring_age_flag"
down_revision = "0022_add_total_rain"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reconductoring",
        sa.Column(
            "for_reconductoring_age", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade():
    op.drop_column("reconductoring", "for_reconductoring_age")
