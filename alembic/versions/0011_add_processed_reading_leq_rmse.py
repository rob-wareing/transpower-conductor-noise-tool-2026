"""add processed_reading.leq_rmse column

Revision ID: 0011_add_leq_rmse
Revises: 0010_add_detection
Create Date: 2026-07-31

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_add_leq_rmse"
down_revision = "0010_add_detection"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "processed_reading",
        sa.Column("leq_rmse", sa.Numeric(5, 2), nullable=True),
    )


def downgrade():
    op.drop_column("processed_reading", "leq_rmse")
