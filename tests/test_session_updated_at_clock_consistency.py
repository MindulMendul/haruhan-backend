import asyncio
import datetime as datetime_module

import app.core.clock as clock_module
from app.repositories.interview_practice_repository import InterviewPracticeSessionRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository


def _freeze_app_clock(monkeypatch, fixed_now: datetime_module.datetime) -> None:
    """app.core.clock.utcnow_naive()가 항상 fixed_now를 반환하게 고정한다.

    `mapped_column(default=utcnow_naive, onupdate=utcnow_naive)`에 넘긴 함수
    객체는 클래스 정의 시점에 SQLAlchemy의 CallableColumnDefault에 그대로
    붙잡혀서, `app.repositories.*` 쪽에서 `from ... import utcnow_naive`로
    가져온 이름이나 `app.core.clock.utcnow_naive`라는 이름 자체를 몽키패치해도
    (이미 붙잡은 원래 함수 객체 자체는 안 바뀌므로) ORM 레벨 default/onupdate
    호출에는 전혀 영향을 못 준다. 대신 `utcnow_naive()`의 본문이 자기 모듈
    전역 이름 `datetime`(`from datetime import datetime`)을 매 호출마다 새로
    조회하는 것을 이용해, `app.core.clock.datetime`을 `.now()`가 고정값을
    반환하는 가짜 클래스로 바꿔치기한다 - 이러면 이 함수 객체가 어디서
    호출되든(ORM default=/onupdate=, touch()의 직접 호출 등) 전부 같은 고정
    시각을 보게 된다. (SQLAlchemy Column.default/.onupdate의 `.arg`를 직접
    몽키패치하는 방식도 격리 실행에서는 동작했지만, 다른 테스트 파일들이
    같은 테이블에 실제 INSERT를 먼저 실행해둔 뒤에는 이 패치가 반영되지
    않는 경우가 있어 - 정확한 SQLAlchemy 내부 캐싱 메커니즘까지는 특정하지
    못했다 - 전체 스위트에서 간헐적으로 실패했다. 이 함수 자체의 전역 조회를
    이용하는 방식은 SQLAlchemy 내부 상태를 전혀 건드리지 않아 그 문제가
    없다.)
    """
    fixed_aware = fixed_now.replace(tzinfo=datetime_module.timezone.utc)

    class _FrozenDatetime(datetime_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_aware

    monkeypatch.setattr(clock_module, "datetime", _FrozenDatetime)


def test_study_session_update_title_uses_the_same_clock_as_touch(db_session_factory, monkeypatch):
    """206라운드: StudySession.updated_at은 원래 server_default/onupdate=func.now()
    (DB 서버 자신의 클럭)였는데, touch()(새 메시지 추가 시 호출)는 그 컬럼을
    utcnow_naive()(파이썬 쪽 클럭)로 직접 덮어쓰는 반면 update_title()(이름 변경)은
    이 컬럼을 건드리지 않고 그대로 onupdate=func.now()에 맡겨져 있었다 - 같은 컬럼이
    호출부에 따라 서로 다른 두 물리적 시계 중 하나로 채워졌다. 202라운드가 고친 세션
    timezone GUC 문제(타임존 이름표가 잘못돼 값 자체가 어긋나던 문제)와 달리, 두
    시계가 올바르게 UTC로 합의하고 있어도 서로 다른 물리적 기계인 이상 완벽히
    동기화된다는 보장은 없어(NTP 드리프트, 관리형 DB가 이 앱과 별도 호스트라는 점
    등), list_for_user()의 "최근 순" 정렬이 거의 동시에 일어난 touch()/update_
    title() 사이에서 뒤집힐 수 있었다.

    updated_at을 default/onupdate=utcnow_naive로 바꿔, update_title()도 이제
    SQLAlchemy의 ORM 레벨 onupdate(DB 트리거가 아니라 UPDATE를 실제로 낼 때 파이썬
    콜러블을 호출해 SET 절에 넣는 동작)를 통해 touch()와 정확히 같은 파이썬 클럭을
    쓰는지 확인한다."""
    fixed_now = datetime_module.datetime(2030, 5, 17, 12, 0, 0)
    _freeze_app_clock(monkeypatch, fixed_now)

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            sessions = StudySessionRepository(session)
            study_session = await sessions.create(user_id=user.id, title="원래 제목", model="m")
            await session.commit()
            assert study_session.updated_at == fixed_now  # INSERT via default=

            await sessions.touch(study_session)
            await session.commit()
            assert study_session.updated_at == fixed_now  # touch()의 명시적 대입

            await sessions.update_title(study_session, "바뀐 제목")
            await session.commit()
            return study_session.updated_at

    updated_at = asyncio.run(_run())
    # update_title()은 updated_at을 직접 대입하지 않는데도, onupdate=utcnow_naive
    # 덕분에 touch()와 정확히 같은(고정된) 값이 나와야 한다 - 여전히 DB 자신의
    # 클럭(SQLite의 실제 CURRENT_TIMESTAMP)에 맡겨져 있었다면 이 고정값과 달랐을
    # 것이다.
    assert updated_at == fixed_now


def test_interview_practice_session_update_topic_uses_the_same_clock_as_touch(
    db_session_factory, monkeypatch
):
    """206라운드: interview_practice_session.py의 InterviewPracticeSession.updated_at도
    같은 이유(study_session.py 쪽 테스트 docstring 참고)로 같은 수정을 적용했다 -
    touch()/update_topic() 둘 다 같은 파이썬 클럭을 쓰는지 확인한다."""
    fixed_now = datetime_module.datetime(2030, 5, 17, 12, 0, 0)
    _freeze_app_clock(monkeypatch, fixed_now)

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            sessions = InterviewPracticeSessionRepository(session)
            practice_session = await sessions.create(user_id=user.id, topic="원래 주제", model="m")
            await session.commit()
            assert practice_session.updated_at == fixed_now

            await sessions.touch(practice_session)
            await session.commit()
            assert practice_session.updated_at == fixed_now

            await sessions.update_topic(practice_session, "바뀐 주제")
            await session.commit()
            return practice_session.updated_at

    updated_at = asyncio.run(_run())
    assert updated_at == fixed_now
