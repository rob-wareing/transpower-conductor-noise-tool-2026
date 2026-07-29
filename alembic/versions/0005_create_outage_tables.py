"""create outage_type and outage tables

Revision ID: 0005_create_outage_tables
Revises: 0004_create_reading_table
Create Date: 2026-07-29

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_create_outage_tables"
down_revision = "0004_create_reading_table"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outage_type",
        sa.Column("outage_type", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("outage_type"),
    )
    op.create_table(
        "outage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("outage_type", sa.String(length=20), nullable=False),
        sa.Column("start_datetime", sa.DateTime(), nullable=False),
        sa.Column("end_datetime", sa.DateTime(), nullable=False),
        sa.Column("notes", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["outage_type"], ["outage_type.outage_type"]),
    )


def downgrade():
    op.drop_table("outage")
    op.drop_table("outage_type")
