"""add measurement_duration_minutes to conductor_summary's key

Revision ID: 0013_add_summary_duration
Revises: 0012_create_conductor
Create Date: 2026-08-02

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0013_add_summary_duration"
down_revision = "0012_create_conductor"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conductor_summary",
        sa.Column(
            "measurement_duration_minutes", sa.Integer(), nullable=False, server_default="15"
        ),
    )
    # DROP PRIMARY KEY + ADD PRIMARY KEY must be a single ALTER TABLE
    # statement, not two separate ones (op.drop_constraint followed by
    # op.create_primary_key) - MySQL only validates that noise_site_id (the
    # FK column) still has a covering index against the *final* state of a
    # single ALTER TABLE, not against the intermediate state between two
    # separate statements, and errors with "Cannot drop index 'PRIMARY':
    # needed in a foreign key constraint" if split.
    op.execute(
        "ALTER TABLE conductor_summary "
        "DROP PRIMARY KEY, "
        "ADD PRIMARY KEY (noise_site_id, detection_logic, measurement_duration_minutes)"
    )


def downgrade():
    op.execute(
        "ALTER TABLE conductor_summary "
        "DROP PRIMARY KEY, "
        "ADD PRIMARY KEY (noise_site_id, detection_logic)"
    )
    op.drop_column("conductor_summary", "measurement_duration_minutes")
