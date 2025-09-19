"""create images table

Revision ID: 20250916_0001
Revises: 
Create Date: 2025-09-16 00:01:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20250916_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    image_status = postgresql.ENUM('NEW', 'PROCESSING', 'DONE', 'ERROR', name='image_status', create_type=True)
    image_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("status", postgresql.ENUM(name='image_status', create_type=False), nullable=False),
        sa.Column("original_url", sa.String(length=2048), nullable=False),
        sa.Column("thumbnails", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
    )


def downgrade() -> None:
    op.drop_table("images")
    image_status = postgresql.ENUM('NEW', 'PROCESSING', 'DONE', 'ERROR', name='image_status', create_type=True)
    image_status.drop(op.get_bind(), checkfirst=True)
