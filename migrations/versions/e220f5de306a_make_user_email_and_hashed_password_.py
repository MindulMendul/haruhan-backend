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
    """Downgrade schema.

    이 upgrade()가 email/hashed_password를 nullable로 바꾼 건 게스트 계정
    (email=NULL, hashed_password=NULL - AuthService.create_guest_session()이
    만드는, 로그인 폼 없이 시작하는 이 앱의 기본/추천 온보딩 경로)을 위해서다.
    그런데 이 downgrade()는 그 사실을 무시하고 두 컬럼을 그냥 NOT NULL로
    되돌리려 한다 - 게스트 계정이 하나라도 있으면(실사용 배포에서는 사실상
    항상 있음, 159라운드 참고) `ALTER TABLE ... SET NOT NULL`이 그 자리에서
    `NotNullViolationError`로 실패한다. 로컬 Postgres 16에 게스트 행 하나만
    넣고 직접 재현해 확인했다 - 아무 안내 없이 로우레벨 asyncpg 스택트레이스
    만 남기고 죽는다.

    이 downgrade를 "성공"시키려면 게스트 계정을 지우거나(데이터 손실) 가짜
    email/비밀번호를 채워 넣어야(더 나쁨) 하는데, 둘 다 자동으로 할 수 있는
    일이 아니다 - 180라운드가 CONCURRENTLY 인덱스 마이그레이션을 "강제로
    성공"시키는 대신 "재배포하면 스스로 복구"되게 고친 것과 같은 철학으로,
    여기서는 원인이 자명한 명시적 에러로 먼저 막아 로우레벨 스택트레이스
    대신 무엇을 해야 하는지 바로 알 수 있게 한다.
    """
    bind = op.get_bind()
    has_guest = bind.execute(
        sa.text("SELECT 1 FROM users WHERE email IS NULL OR hashed_password IS NULL LIMIT 1")
    ).first()
    if has_guest is not None:
        raise RuntimeError(
            "e220f5de306a downgrade가 막혔습니다: email 또는 hashed_password가 "
            "NULL인 게스트 계정이 존재합니다. 이 리비전으로 되돌리면 그 계정들이 "
            "복원되는 NOT NULL 제약을 위반합니다. 게스트 계정을 수동으로 정리한 "
            "뒤 다시 시도하세요(자동으로 지우지 않는 이유: 데이터 손실이라 "
            "운영자의 명시적 판단이 필요합니다)."
        )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("hashed_password", existing_type=sa.VARCHAR(length=255), nullable=False)
        batch_op.alter_column("email", existing_type=sa.VARCHAR(length=255), nullable=False)
