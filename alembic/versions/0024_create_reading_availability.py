"""create reading_availability table

Revision ID: 0024_reading_availability
Revises: 0023_reconductoring_age_flag
Create Date: 2026-08-22

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0024_reading_availability"
down_revision = "0023_reconductoring_age_flag"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reading_availability",
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("min_datetime", sa.DateTime(), nullable=False),
        sa.Column("max_datetime", sa.DateTime(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("noise_site_id"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("reading_availability")
