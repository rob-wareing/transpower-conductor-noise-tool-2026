"""create processed_reading table

Revision ID: 0003_create_processed_reading
Revises: 0002_create_user_table
Create Date: 2026-07-28

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_create_processed_reading"
down_revision = "0002_create_user_table"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "processed_reading",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("datetime", sa.DateTime(), nullable=False),
        sa.Column("l90", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("tone_100hz", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("tone_200hz", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("rain1", sa.Numeric(precision=3, scale=1), nullable=False),
        sa.Column("rain2", sa.Numeric(precision=3, scale=1), nullable=False),
        sa.Column("is_wet", sa.Boolean(), nullable=False),
        sa.Column("include", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("processed_reading")
