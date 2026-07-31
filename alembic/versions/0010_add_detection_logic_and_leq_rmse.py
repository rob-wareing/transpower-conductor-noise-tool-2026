"""add processed_reading.detection_logic and reading.leq_rmse columns

Revision ID: 0010_add_detection
Revises: 0009_add_duration
Create Date: 2026-07-31

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010_add_detection"
down_revision = "0009_add_duration"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "processed_reading",
        sa.Column("detection_logic", sa.String(20), nullable=False, server_default="original"),
    )
    op.add_column(
        "reading",
        sa.Column("leq_rmse", sa.Numeric(5, 2), nullable=True),
    )


def downgrade():
    op.drop_column("reading", "leq_rmse")
    op.drop_column("processed_reading", "detection_logic")
