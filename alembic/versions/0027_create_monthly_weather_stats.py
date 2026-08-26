"""create monthly_weather_stats table

Revision ID: 0027_monthly_weather_stats
Revises: 0026_monthly_rainfall_year
Create Date: 2026-08-21

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0027_monthly_weather_stats"
down_revision = "0026_monthly_rainfall_year"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "monthly_weather_stats",
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("min_rain_mm", sa.Numeric(4, 2), nullable=True),
        sa.Column("max_rain_mm", sa.Numeric(4, 2), nullable=True),
        sa.Column("avg_rain_mm", sa.Numeric(4, 2), nullable=True),
        sa.Column("min_wind_speed", sa.Numeric(4, 1), nullable=True),
        sa.Column("max_wind_speed", sa.Numeric(4, 1), nullable=True),
        sa.Column("avg_wind_speed", sa.Numeric(4, 1), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("noise_site_id", "year", "month"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("monthly_weather_stats")
