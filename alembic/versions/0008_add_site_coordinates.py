"""add latitude/longitude columns to site

Revision ID: 0008_add_site_coords
Revises: 0007_create_historical
Create Date: 2026-07-30

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_add_site_coords"
down_revision = "0007_create_historical"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("site", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("site", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))


def downgrade():
    op.drop_column("site", "longitude")
    op.drop_column("site", "latitude")
