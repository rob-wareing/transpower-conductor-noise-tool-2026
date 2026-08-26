"""add historical_line_color column to site

Revision ID: 0028_site_historical_line_color
Revises: 0027_monthly_weather_stats
Create Date: 2026-08-22

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0028_site_historical_line_color"
down_revision = "0027_monthly_weather_stats"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "site",
        sa.Column("historical_line_color", sa.String(7), nullable=True),
    )


def downgrade():
    op.drop_column("site", "historical_line_color")
