"""create wind_rose table

Revision ID: 0017_create_wind_rose
Revises: 0016_add_site_is_ignored
Create Date: 2026-08-04

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0017_create_wind_rose"
down_revision = "0016_add_site_is_ignored"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wind_rose",
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("direction_sector", sa.String(3), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("avg_wind_speed", sa.Numeric(4, 1), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("noise_site_id", "direction_sector"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("wind_rose")
