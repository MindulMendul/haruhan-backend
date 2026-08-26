"""add composite index on knowledge_chunks user_id embedding_model created_at

Revision ID: f8c776ddf837
Revises: 089b9a2d134f
Create Date: 2026-08-25 22:34:21.665912

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8c776ddf837'
down_revision: Union[str, Sequence[str], None] = '089b9a2d134f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # CREATE INDEX(비-concurrent)는 인덱스 빌드가 끝날 때까지 이 테이블에 대한
    # 쓰기(INSERT/UPDATE/DELETE)를 막는 락을 그대로 들고 있는다. knowledge_chunks
    # 는 학습챗 메시지/면접 복기/퀴즈 소스/면접연습 답변마다 계속 쌓이는 RAG 색인
    # 테이블이라 서비스가 커질수록 테이블도 커지므로, 이 마이그레이션을 그대로
    # 적용하면 배포 순간 RagService.index_content()가 하는 쓰기가 전부 멈춘다.
    # CONCURRENTLY로 만들면 이 락 없이(그 대신 테이블을 두 번 스캔하는 비용으로)
    # 인덱스를 빌드할 수 있는데, Postgres는 CREATE INDEX CONCURRENTLY를 트랜잭션
    # 블록 안에서 실행하는 것 자체를 허용하지 않는다 - alembic이 기본으로 모든
    # 마이그레이션을 트랜잭션 안에서 실행하므로(migrations/env.py의
    # context.begin_transaction()), autocommit_block()으로 이 문장만 트랜잭션
    # 밖에서 실행되도록 감싼다.
    with op.get_context().autocommit_block():
        op.create_index(
            'ix_knowledge_chunks_user_id_embedding_model_created_at',
            'knowledge_chunks',
            ['user_id', 'embedding_model', 'created_at'],
            unique=False,
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    # DROP INDEX CONCURRENTLY도 같은 이유로 트랜잭션 밖에서 실행해야 한다.
    with op.get_context().autocommit_block():
        op.drop_index(
            'ix_knowledge_chunks_user_id_embedding_model_created_at',
            table_name='knowledge_chunks',
            postgresql_concurrently=True,
        )
