"""add year to monthly_rainfall, widen primary key

Revision ID: 0026_monthly_rainfall_year
Revises: 0025_wind_rose_year_month
Create Date: 2026-08-21

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0026_monthly_rainfall_year"
down_revision = "0025_wind_rose_year_month"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE monthly_rainfall "
        "DROP PRIMARY KEY, "
        "ADD COLUMN year INT NOT NULL DEFAULT 0, "
        "ADD PRIMARY KEY (noise_site_id, year, month)"
    )


def downgrade():
    op.execute(
        "ALTER TABLE monthly_rainfall "
        "DROP PRIMARY KEY, "
        "DROP COLUMN year, "
        "ADD PRIMARY KEY (noise_site_id, month)"
    )
