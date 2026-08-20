"""add total_rain column to monthly_rainfall

Revision ID: 0022_add_total_rain
Revises: 0021_grease_description
Create Date: 2026-08-07

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0022_add_total_rain"
down_revision = "0021_grease_description"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "monthly_rainfall",
        sa.Column(
            "total_rain", sa.Numeric(8, 2), nullable=False, server_default=sa.text("0")
        ),
    )


def downgrade():
    op.drop_column("monthly_rainfall", "total_rain")
