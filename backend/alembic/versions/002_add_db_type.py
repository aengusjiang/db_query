"""Add db_type column to databaseconnections.

Aligns the table with the DatabaseConnection SQLModel, which defines
db_type (postgresql/mysql) but was missing from the 001 migration.

Revision ID: 002
Revises: 001
Create Date: 2026-08-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add db_type to databaseconnections."""
    with op.batch_alter_table('databaseconnections') as batch_op:
        batch_op.add_column(
            sa.Column(
                'db_type',
                sa.String(length=20),
                nullable=False,
                server_default='postgresql',
            )
        )


def downgrade() -> None:
    """Remove db_type from databaseconnections."""
    with op.batch_alter_table('databaseconnections') as batch_op:
        batch_op.drop_column('db_type')
