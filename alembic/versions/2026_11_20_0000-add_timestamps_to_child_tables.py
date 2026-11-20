"""add timestamp columns to child tables

Adds created_at/updated_at (TimestampMixin) to addresses, categories,
product_variants and product_images. cart_items keeps its added_at column
(creation time) and gains updated_at, backfilled from added_at so existing
rows keep their original timestamp.

Revision ID: 002_add_timestamps_to_child_tables
Revises: 001_initial_schema
Create Date: 2026-11-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_add_timestamps_to_child_tables"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIMESTAMP_TABLES = ["addresses", "categories", "product_variants", "product_images"]


def upgrade() -> None:
    # cart_items: keep added_at (creation time), add updated_at backfilled from it.
    op.add_column(
        "cart_items",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("UPDATE cart_items SET updated_at = added_at")
    op.alter_column("cart_items", "updated_at", server_default=None, nullable=False)

    # Remaining tables: both columns, backfilled with the insert time.
    for table in TIMESTAMP_TABLES:
        op.add_column(
            table,
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.add_column(
            table,
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.execute(f"UPDATE {table} SET updated_at = created_at")
        op.alter_column(table, "created_at", server_default=None, nullable=False)
        op.alter_column(table, "updated_at", server_default=None, nullable=False)


def downgrade() -> None:
    for table in TIMESTAMP_TABLES:
        op.drop_column(table, "updated_at")
        op.drop_column(table, "created_at")

    op.drop_column("cart_items", "updated_at")
