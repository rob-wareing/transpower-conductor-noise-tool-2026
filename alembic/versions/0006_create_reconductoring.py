"""create reconductoring table

Revision ID: 0006_create_reconductoring
Revises: 0005_create_outage_tables
Create Date: 2026-07-29

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_create_reconductoring"
down_revision = "0005_create_outage_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reconductoring",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("conductor", sa.String(length=200), nullable=True),
        sa.Column("grease", sa.String(length=50), nullable=True),
        sa.Column("conductor_and_treatment", sa.String(length=200), nullable=True),
        sa.Column("reconductoring_date", sa.Date(), nullable=False),
        sa.Column("plot_linestyle", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("reconductoring")
