import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow_naive
from app.db.base import Base


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # 세션 안의 모든 메시지는 같은 모델을 계속 쓴다 (메시지마다 바꾸지 않음).
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    # 206라운드: DB의 server_default/onupdate=func.now() 대신 파이썬 쪽 utcnow_naive()를
    # 쓴다 - study_session_repository.touch()(새 메시지가 추가될 때마다 호출)는 이미
    # utcnow_naive()로 이 컬럼을 직접 덮어쓰는데, update_title()(이름 변경)은 이 컬럼을
    # 건드리지 않고 그대로 onupdate=func.now()에 맡겨져 있었다 - 즉 같은 컬럼이 호출부에
    # 따라 서로 다른 두 물리적 클럭(앱 호스트의 시스템 시계 vs 이 접속 문자열이 가리키는
    # (보통 이 앱이 직접 프로비저닝하지 않는 관리형) Postgres 인스턴스의 시스템 시계) 중
    # 하나로 채워졌다. 202라운드가 고친 세션 timezone GUC 문제(타임존 "이름표"가 잘못돼
    # 값 자체가 몇 시간씩 어긋나던 문제)와는 별개로, 두 시계가 올바르게 UTC로 합의하고
    # 있어도 서로 다른 물리적 기계인 이상 완벽히 동기화된다는 보장은 없다(NTP 드리프트,
    # 관리형 DB의 클럭이 이 앱과 별도로 관리됨 등) - list_for_user()가 이 컬럼으로
    # "최근 순" 정렬을 하므로, 두 클럭이 어긋난 채로 거의 동시에 각각 touch()/update_
    # title()이 일어나면 방금 실제로 채팅한 세션이 그보다 먼저 이름만 바꾼 세션보다
    # 아래로 정렬될 수 있다. QuizAttempt.submitted_at/StudyMessage.created_at도 (다른
    # 이유 - SQLite의 CURRENT_TIMESTAMP가 초 단위라 짧은 간격의 재제출 순서를 못
    # 구분하던 문제 - 로) 이미 이 패턴(server_default 대신 default=utcnow_naive)을
    # 쓰고 있다. onupdate=utcnow_naive는 SQLAlchemy가 UPDATE를 실제로 낼 때(title만
    # 바뀌어도) 파이썬 콜러블을 호출해 그 값을 SET 절에 넣는 ORM 레벨 동작이라(DB
    # 트리거가 아님), update_title()도 이제 자동으로 같은 파이썬 클럭을 쓰게 된다 -
    # 마이그레이션의 server_default=CURRENT_TIMESTAMP는 INSERT 시 SQLAlchemy가 항상
    # 명시적 값을 채워 넣어 사실상 안 쓰이는 채로 남아도 무해하다(QuizAttempt가 이미
    # DDL을 안 건드리고 이 전환을 한 것과 같음).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False
    )
