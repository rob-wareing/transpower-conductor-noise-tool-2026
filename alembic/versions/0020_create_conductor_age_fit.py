"""create conductor_age_fit table

Revision ID: 0020_create_age_fit
Revises: 0019_add_reconductoring_age
Create Date: 2026-08-05

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0020_create_age_fit"
down_revision = "0019_add_reconductoring_age"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conductor_age_fit",
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("detection_logic", sa.String(20), nullable=False),
        sa.Column("metric", sa.String(20), nullable=False),
        sa.Column("slope", sa.Numeric(10, 4), nullable=False),
        sa.Column("intercept", sa.Numeric(10, 4), nullable=False),
        sa.Column("r_squared", sa.Numeric(5, 4), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("noise_site_id", "detection_logic", "metric"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("conductor_age_fit")
