"""add year/month to wind_rose, widen primary key

Revision ID: 0025_wind_rose_year_month
Revises: 0024_reading_availability
Create Date: 2026-08-21

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0025_wind_rose_year_month"
down_revision = "0024_reading_availability"
branch_labels = None
depends_on = None


def upgrade():
    # Drop+add of a composite primary key must be one multi-clause
    # ALTER TABLE, not separate statements - MySQL rejects a table with no
    # primary key even transiently within a migration.
    op.execute(
        "ALTER TABLE wind_rose "
        "DROP PRIMARY KEY, "
        "ADD COLUMN year INT NOT NULL DEFAULT 0, "
        "ADD COLUMN month INT NOT NULL DEFAULT 0, "
        "ADD PRIMARY KEY (noise_site_id, year, month, direction_sector)"
    )


def downgrade():
    op.execute(
        "ALTER TABLE wind_rose "
        "DROP PRIMARY KEY, "
        "DROP COLUMN year, "
        "DROP COLUMN month, "
        "ADD PRIMARY KEY (noise_site_id, direction_sector)"
    )
