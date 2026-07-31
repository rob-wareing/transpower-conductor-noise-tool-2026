"""add measurement_duration_minutes columns to reading and processed_reading

Revision ID: 0009_add_duration
Revises: 0008_add_site_coords
Create Date: 2026-07-31

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_add_duration"
down_revision = "0008_add_site_coords"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reading",
        sa.Column("measurement_duration_minutes", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "processed_reading",
        sa.Column("measurement_duration_minutes", sa.Integer(), nullable=False, server_default="15"),
    )


def downgrade():
    op.drop_column("processed_reading", "measurement_duration_minutes")
    op.drop_column("reading", "measurement_duration_minutes")
