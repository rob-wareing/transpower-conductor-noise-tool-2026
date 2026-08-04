"""add composite index on processed_reading(noise_site_id, datetime)

Revision ID: 0015_add_reading_site_dt_idx
Revises: 0014_create_rain_rate_fit
Create Date: 2026-08-03

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0015_add_reading_site_dt_idx"
down_revision = "0014_create_rain_rate_fit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_processed_reading_site_datetime",
        "processed_reading",
        ["noise_site_id", "datetime"],
    )


def downgrade():
    op.drop_index("ix_processed_reading_site_datetime", table_name="processed_reading")
