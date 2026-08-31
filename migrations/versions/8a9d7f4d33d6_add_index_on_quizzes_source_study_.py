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
    # CONCURRENTLY 빌드가 중간에 끊기면(배포 타임아웃, 컨테이너 강제 종료, DB
    # 커넥션 유실 등) Postgres는 그 인덱스를 지우지 않고 indisvalid=false인
    # 채로 남긴다 - 다음 배포가 이 마이그레이션을 그대로 재실행하면
    # DuplicateTableError로 실패하고, 그 뒤로는 알렘빅이 이 리비전에 영영
    # 멈춘 채 재배포할 때마다 계속 같은 에러를 낸다(DBA가 수동으로 접속해
    # DROP INDEX CONCURRENTLY를 실행해야만 풀림). 로컬 Postgres 16으로 직접
    # 재현했다 - 이 CREATE INDEX CONCURRENTLY가 다른 트랜잭션을 기다리는
    # 도중 그 백엔드를 강제 종료하면 indisvalid=false/indisready=false인
    # 인덱스가 남고, 그 상태로 `alembic upgrade head`를 다시 돌리면 정확히
    # 이 DuplicateTableError로 막힌다(IF NOT EXISTS를 붙이면 조용히 스킵될
    # 뿐 인덱스는 여전히 못 쓰는 채로 남아 오히려 더 나쁘다는 것도 확인함).
    # 빌드 직전에 무효한 이전 시도를 먼저 정리하면(멀쩡한 인덱스가 있으면
    # 이름이 다르니 영향 없고, 없으면 아무 일도 안 함) 재배포만으로 스스로
    # 복구된다 - DROP INDEX CONCURRENTLY도 트랜잭션 밖에서 실행해야 해서
    # 같은 autocommit_block() 안에 둔다.
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_quizzes_source_study_session_id")
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
