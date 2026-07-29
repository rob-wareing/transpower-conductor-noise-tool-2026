"""create historical_result table

Revision ID: 0007_create_historical
Revises: 0006_create_reconductoring
Create Date: 2026-07-30

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_create_historical"
down_revision = "0006_create_reconductoring"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "historical_result",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("period_length", sa.Integer(), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("leq_adj", sa.Numeric(4, 1), nullable=True),
        sa.Column("tone_100hz", sa.Numeric(4, 2), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("historical_result")
