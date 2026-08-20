"""create grease_description table

Revision ID: 0021_grease_description
Revises: 0020_create_age_fit
Create Date: 2026-08-06

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0021_grease_description"
down_revision = "0020_create_age_fit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "grease_description",
        sa.Column("grease", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("grease"),
    )


def downgrade():
    op.drop_table("grease_description")
