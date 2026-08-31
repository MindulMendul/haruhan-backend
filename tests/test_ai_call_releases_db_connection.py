import asyncio
import json
import os
import tempfile

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.interview_practice_service import InterviewPracticeService
from app.services.quiz_service import QuizService
from app.services.rag_service import RagService
from app.services.study_service import StudyService


class FakeEmbeddingOllamaService:
    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


class _CheckingOllamaService:
    """실제 AI 호출(chat/generate) 시점에 커넥션 풀에서 체크아웃된 커넥션
    개수를 그 자리에서 기록한다 - retrieve_relevant()가 한 DB 조회 뒤에도
    커밋/롤백을 안 하면 SQLAlchemy가 트랜잭션이 끝날 때까지 커넥션을 계속
    붙들고 있어서, 이 시점에 커넥션이 여전히 체크아웃돼 있다."""

    def __init__(self, engine):
        self.engine = engine
        self.checked_out_during_call: int | None = None

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]

    async def chat(self, messages, model):
        self.checked_out_during_call = self.engine.pool.checkedout()
        return "AI 응답"

    async def chat_stream(self, messages, model):
        self.checked_out_during_call = self.engine.pool.checkedout()
        for chunk in ["AI", "응답"]:
            yield chunk

    async def generate(self, prompt, model):
        self.checked_out_during_call = self.engine.pool.checkedout()
        return "첫 질문"

    async def generate_json(self, prompt, model, schema):
        self.checked_out_during_call = self.engine.pool.checkedout()
        return json.dumps(
            {
                "questions": [
                    {
                        "question": "질문",
                        "choices": ["가", "나"],
                        "correct_answer": "가",
                        "explanation": "설명",
                    }
                ]
            }
        )


def _make_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    # 풀 크기 1로 실제 SQLAlchemy 커넥션 풀을 만들어, AI 호출이 실행되는
    # 시점에 체크아웃된 커넥션 수를 직접 셀 수 있게 한다 - :memory:+
    # StaticPool을 쓰는 conftest의 기본 client 픽스처는 커넥션이 하나로
    # 고정돼 있어 이 검증 자체가 불가능하다(test_auth.py의 동시성 테스트와
    # 같은 이유로 파일 기반 SQLite + pool_size를 쓴다).
    url = f"sqlite+aiosqlite:///{path}"
    engine = create_async_engine(url, pool_size=1, max_overflow=0)
    return engine, path


def test_send_message_releases_db_connection_before_ai_call():
    """study_service.send_message()가 retrieve_relevant() 이후, 몇 초~몇십 초
    걸릴 수 있는 AI 호출(chat()) 전에 DB 커넥션을 커넥션 풀에 돌려주는지
    확인한다 - 안 그러면 동시에 여러 명이 채팅 중일 때 커넥션 풀이 순식간에
    고갈돼 이 요청과 전혀 무관한 다른 요청까지 타임아웃으로 실패한다(실제
    Postgres로 재현해 확인한 증상)."""
    settings = get_settings()
    engine, path = _make_engine()

    async def _run():
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                user = await UserRepository(session).create_guest()
                await session.commit()
                study_session = await StudySessionRepository(session).create(
                    user_id=user.id, title="풀 테스트", model="qwen2.5:3b"
                )
                await session.commit()

                fake = _CheckingOllamaService(engine)
                rag = RagService(session=session, ollama_service=fake, settings=settings)
                service = StudyService(
                    session=session, ollama_service=fake, rag_service=rag, settings=settings
                )

                await service.send_message(session_id=study_session.id, user_id=user.id, content="안녕")

            return fake.checked_out_during_call
        finally:
            await engine.dispose()
            if os.path.exists(path):
                os.unlink(path)

    checked_out_during_call = asyncio.run(_run())
    assert checked_out_during_call == 0


def test_stream_message_releases_db_connection_before_ai_call():
    """study_service.stream_message()(WebSocket 스트리밍 버전)도 같은 이유로
    (send_message 테스트 docstring 참고) retrieve_relevant() 이후 AI
    호출(chat_stream()) 전에 DB 커넥션을 커넥션 풀에 돌려주는지 확인한다."""
    settings = get_settings()
    engine, path = _make_engine()

    async def _run():
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                user = await UserRepository(session).create_guest()
                await session.commit()
                study_session = await StudySessionRepository(session).create(
                    user_id=user.id, title="풀 테스트", model="qwen2.5:3b"
                )
                await session.commit()

                fake = _CheckingOllamaService(engine)
                rag = RagService(session=session, ollama_service=fake, settings=settings)
                service = StudyService(
                    session=session, ollama_service=fake, rag_service=rag, settings=settings
                )

                async for _event_type, _data in service.stream_message(
                    session_id=study_session.id, user_id=user.id, content="안녕"
                ):
                    pass

            return fake.checked_out_during_call
        finally:
            await engine.dispose()
            if os.path.exists(path):
                os.unlink(path)

    checked_out_during_call = asyncio.run(_run())
    assert checked_out_during_call == 0


def test_create_quiz_from_study_session_releases_db_connection_before_ai_call():
    """quiz_service.create_quiz()가 study_session_id로 퀴즈를 만들 때도 같은
    이유로(위 테스트들 docstring 참고) 학습 세션 조회(get_for_user/list_
    for_session)로 source_text를 조립한 뒤, 몇 초~몇십 초(재시도 포함 최대
    2분) 걸릴 수 있는 AI 호출(generate_json()) 전에 DB 커넥션을 커넥션
    풀에 돌려주는지 확인한다. source_text를 직접 붙여넣는 경로는 애초에
    이 분기의 DB 조회 자체가 없어 이 문제가 없다(재현 과정에서 함께
    확인함) - study_session_id 경로만 대상이다."""
    settings = get_settings()
    engine, path = _make_engine()

    async def _run():
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                user = await UserRepository(session).create_guest()
                await session.commit()
                study_session = await StudySessionRepository(session).create(
                    user_id=user.id, title="풀 테스트", model="qwen2.5:3b"
                )
                await session.commit()
                await StudyMessageRepository(session).create(
                    session_id=study_session.id, role="user", content="안녕"
                )
                await session.commit()

                fake = _CheckingOllamaService(engine)
                rag = RagService(session=session, ollama_service=fake, settings=settings)
                service = QuizService(
                    session=session, ollama_service=fake, rag_service=rag, settings=settings
                )

                await service.create_quiz(
                    user_id=user.id,
                    title="퀴즈",
                    study_session_id=study_session.id,
                    source_text=None,
                    question_count=1,
                    model="qwen2.5:3b",
                )

            return fake.checked_out_during_call
        finally:
            await engine.dispose()
            if os.path.exists(path):
                os.unlink(path)

    checked_out_during_call = asyncio.run(_run())
    assert checked_out_during_call == 0


def test_create_practice_session_releases_db_connection_before_ai_call():
    """interview_practice_service.create_session()도 같은 이유로(위 테스트
    docstring 참고) retrieve_relevant() 이후 AI 호출(generate()) 전에 DB
    커넥션을 커넥션 풀에 돌려주는지 확인한다."""
    settings = get_settings()
    engine, path = _make_engine()

    async def _run():
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session:
                user = await UserRepository(session).create_guest()
                await session.commit()

                fake = _CheckingOllamaService(engine)
                rag = RagService(session=session, ollama_service=fake, settings=settings)
                service = InterviewPracticeService(
                    session=session, ollama_service=fake, settings=settings, rag_service=rag
                )

                await service.create_session(user_id=user.id, topic="백엔드 개발자", model="qwen2.5:3b")

            return fake.checked_out_during_call
        finally:
            await engine.dispose()
            if os.path.exists(path):
                os.unlink(path)

    checked_out_during_call = asyncio.run(_run())
    assert checked_out_during_call == 0
