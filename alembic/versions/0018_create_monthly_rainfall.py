"""create monthly_rainfall table

Revision ID: 0018_create_monthly_rainfall
Revises: 0017_create_wind_rose
Create Date: 2026-08-04

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0018_create_monthly_rainfall"
down_revision = "0017_create_wind_rose"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monthly_rainfall",
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("avg_rain_mm", sa.Numeric(4, 2), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("noise_site_id", "month"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("monthly_rainfall")
