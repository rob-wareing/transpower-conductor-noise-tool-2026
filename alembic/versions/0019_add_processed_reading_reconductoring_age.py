"""add processed_reading.reconductoring_age column

Revision ID: 0019_add_reconductoring_age
Revises: 0018_create_monthly_rainfall
Create Date: 2026-08-05

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0019_add_reconductoring_age"
down_revision = "0018_create_monthly_rainfall"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "processed_reading",
        sa.Column("reconductoring_age", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("processed_reading", "reconductoring_age")
