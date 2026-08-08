"""Create the Tahr Desk 1.0 schema.

Revision ID: 0001_tahr_desk
Revises:
Create Date: 2026-08-08
"""

from alembic import op

from app.models import SQLModel

revision = "0001_tahr_desk"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    SQLModel.metadata.create_all(bind)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_case_subject_trgm "
        "ON service_case USING gin (lower(subject) gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_case_location_trgm "
        "ON service_case USING gin (lower(location_text) gin_trgm_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_case_location_trgm")
    op.execute("DROP INDEX IF EXISTS ix_case_subject_trgm")
    SQLModel.metadata.drop_all(bind)
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
