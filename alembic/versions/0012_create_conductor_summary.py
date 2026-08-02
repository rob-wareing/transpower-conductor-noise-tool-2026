"""create conductor_summary table

Revision ID: 0012_create_conductor
Revises: 0011_add_leq_rmse
Create Date: 2026-08-02

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0012_create_conductor"
down_revision = "0011_add_leq_rmse"
branch_labels = None
depends_on = None

METRICS = ["l90", "tone_100hz", "tone_200hz"]
STATS = ["mean", "max", "min", "median", "q1", "q3"]


def upgrade():
    stat_columns = [
        sa.Column(f"{metric}_{stat}", sa.Numeric(6, 2), nullable=False)
        for metric in METRICS
        for stat in STATS
    ]
    op.create_table(
        "conductor_summary",
        sa.Column("noise_site_id", sa.Integer(), nullable=False),
        sa.Column("detection_logic", sa.String(20), nullable=False),
        *stat_columns,
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("noise_site_id", "detection_logic"),
        sa.ForeignKeyConstraint(
            ["noise_site_id"],
            ["site.noise_site_id"],
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    )


def downgrade():
    op.drop_table("conductor_summary")
