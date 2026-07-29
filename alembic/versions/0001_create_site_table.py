"""create site table

Revision ID: 0001_create_site_table
Revises:
Create Date: 2026-07-28

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_create_site_table"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "site",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("site_name", sa.String(length=100), nullable=False),
        sa.Column("site_code", sa.String(length=20), nullable=True),
        sa.Column("plot_color", sa.String(length=7), nullable=True),
        sa.Column("height_adj_db", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("data_folder", sa.String(length=500), nullable=True),
        sa.Column("report_folder", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("noise_site_id"),
    )


def downgrade():
    op.drop_table("site")
