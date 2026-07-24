"""make user email and hashed_password nullable for guest accounts

Revision ID: e220f5de306a
Revises: e759333dc5dc
Create Date: 2026-07-23 10:21:30.610980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e220f5de306a'
down_revision: Union[str, Sequence[str], None] = 'e759333dc5dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite는 ALTER COLUMN을 지원하지 않아 batch mode(테이블 재생성)를 써야 한다.
    # Postgres 등 다른 방언에서는 batch_alter_table이 그냥 일반 ALTER COLUMN으로 컴파일된다.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("email", existing_type=sa.VARCHAR(length=255), nullable=True)
        batch_op.alter_column("hashed_password", existing_type=sa.VARCHAR(length=255), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("hashed_password", existing_type=sa.VARCHAR(length=255), nullable=False)
        batch_op.alter_column("email", existing_type=sa.VARCHAR(length=255), nullable=False)
