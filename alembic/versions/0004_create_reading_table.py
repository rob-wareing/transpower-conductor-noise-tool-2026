"""create reading table

Revision ID: 0004_create_reading_table
Revises: 0003_create_processed_reading
Create Date: 2026-07-28

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_create_reading_table"
down_revision = "0003_create_processed_reading"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reading",
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("datetime", sa.DateTime(), nullable=False),
        sa.Column("leq", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("l90", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("leq_80hz", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("leq_100hz", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("leq_125hz", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("leq_160hz", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("leq_200hz", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("leq_250hz", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("wind_speed", sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column("wind_direction", sa.Integer(), nullable=True),
        sa.Column("rain_mm", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.PrimaryKeyConstraint("noise_site_id", "datetime"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("reading")
