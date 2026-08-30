"""add index on quizzes source_study_session_id

Revision ID: 8a9d7f4d33d6
Revises: f8c776ddf837
Create Date: 2026-08-30 17:42:36.074648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a9d7f4d33d6'
down_revision: Union[str, Sequence[str], None] = 'f8c776ddf837'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # CREATE INDEX(비-concurrent)는 인덱스 빌드가 끝날 때까지 이 테이블에 대한
    # 쓰기(INSERT/UPDATE/DELETE)를 막는 락을 그대로 들고 있는다. quizzes는 사용자가
    # 퀴즈를 만들 때마다 계속 쌓이는 테이블이라 서비스가 커질수록 테이블도 커지므로,
    # 이 마이그레이션을 그대로 적용하면 배포 순간 퀴즈 생성/조회가 전부 멈춘다.
    # CONCURRENTLY로 만들면 이 락 없이(그 대신 테이블을 두 번 스캔하는 비용으로)
    # 인덱스를 빌드할 수 있는데, Postgres는 CREATE INDEX CONCURRENTLY를 트랜잭션
    # 블록 안에서 실행하는 것 자체를 허용하지 않는다 - alembic이 기본으로 모든
    # 마이그레이션을 트랜잭션 안에서 실행하므로(migrations/env.py의
    # context.begin_transaction()), autocommit_block()으로 이 문장만 트랜잭션
    # 밖에서 실행되도록 감싼다(f8c776ddf837의 knowledge_chunks 복합 인덱스와 같은 이유).
    with op.get_context().autocommit_block():
        op.create_index(
            op.f('ix_quizzes_source_study_session_id'),
            'quizzes',
            ['source_study_session_id'],
            unique=False,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    # DROP INDEX CONCURRENTLY도 같은 이유로 트랜잭션 밖에서 실행해야 한다.
    with op.get_context().autocommit_block():
        op.drop_index(
            op.f('ix_quizzes_source_study_session_id'),
            table_name='quizzes',
            postgresql_concurrently=True,
        )
