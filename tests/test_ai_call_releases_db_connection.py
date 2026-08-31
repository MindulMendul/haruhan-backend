import asyncio
import json
import os
import tempfile

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.repositories.interview_practice_repository import (
    InterviewPracticeSessionRepository,
    InterviewPracticeTurnRepository,
)
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
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
        self.checked_out_during_embed_calls: list[int] = []

    async def embed(self, text, model):
        # 196라운드: retrieve_relevant()와 index_content() 둘 다 DB 조회
        # (list_for_user/delete_for_source) 직후 곧바로 이 embed() 호출로
        # 넘어가는데, 그 사이 커밋을 안 하면 embed() 도중에도 커넥션이
        # 체크아웃돼 있다 - chat/chat_stream/generate/generate_json만
        # 기록하던 기존 fake는 이 경로를 전혀 검증하지 못했다(193라운드
        # fix가 호출부의 commit()만 확인하고 이 두 메서드 내부의 이 gap을
        # 놓쳤던 이유와 같다). send_message() 한 번에 embed()가 3번(retrieve_
        # relevant() 1번 + index_content() 2번) 불릴 수 있어, 매번의
        # 체크아웃 상태를 전부 리스트에 남긴다 - 마지막 호출 하나만 보면
        # 앞선 호출의 회귀를 놓칠 수 있다.
        self.checked_out_during_embed_calls.append(self.engine.pool.checkedout())
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


def test_send_message_releases_db_connection_before_embed_call():
    """196라운드: retrieve_relevant() 자신도 list_for_user() 조회 뒤
    embed()(Ollama 임베딩 호출) 전에 커밋해서 DB 커넥션을 풀에 돌려주는지
    확인한다 - 193라운드는 send_message()가 retrieve_relevant()가 "돌아온
    뒤" commit()하는 것만 고쳤을 뿐, retrieve_relevant() 자신이 embed()를
    부르는 동안 커넥션을 붙들고 있던 건 못 잡았다(위 chat() 검증만으로는
    이 gap이 안 보인다 - embed()는 그보다 먼저 끝나기 때문). 이 테스트는
    청크를 하나 미리 색인해둬서 retrieve_relevant()가 실제로 embed() 분기까지
    가도록 만든다(색인된 청크가 없으면 embed() 호출 자체가 생략돼 이 gap이
    드러나지 않는다)."""
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
                await KnowledgeChunkRepository(session).create(
                    user_id=user.id,
                    source_type="study_message",
                    source_id=study_session.id,
                    content="기존 기록",
                    embedding=[1.0, 0.0, 0.0],
                    embedding_model=settings.embedding_model,
                )
                await session.commit()

                fake = _CheckingOllamaService(engine)
                rag = RagService(session=session, ollama_service=fake, settings=settings)
                service = StudyService(
                    session=session, ollama_service=fake, rag_service=rag, settings=settings
                )

                await service.send_message(session_id=study_session.id, user_id=user.id, content="안녕")

            return fake.checked_out_during_embed_calls
        finally:
            await engine.dispose()
            if os.path.exists(path):
                os.unlink(path)

    checked_out_during_embed_calls = asyncio.run(_run())
    # retrieve_relevant() 1번 + index_content() 2번(사용자 메시지/AI 응답
    # 각각) = embed() 총 3번. 셋 다 커넥션이 풀려 있어야 한다.
    assert checked_out_during_embed_calls == [0, 0, 0]


def test_complete_practice_session_holds_db_connection_during_embed_call():
    """complete_session()은 193라운드부터 의도적으로 retrieve_relevant() 이후
    (그리고 이제 그 내부의 embed()까지) 커밋하지 않는다 - get_for_user_locked()의
    FOR UPDATE 잠금을 AI 호출 전체 동안 붙들어야 동시 제출/종료를 직렬화하기
    때문이다(interview_practice_service.py의 해당 주석 참고). 이 테스트는 그
    트레이드오프가 앞으로도 실수로 "고쳐지지" 않도록, embed() 도중에도 커넥션이
    여전히 체크아웃돼 있음을(=잠금이 아직 살아있음을) 고정해서 검증한다."""
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

                sessions_repo = InterviewPracticeSessionRepository(session)
                turns_repo = InterviewPracticeTurnRepository(session)
                practice_session = await sessions_repo.create(
                    user_id=user.id, topic="백엔드 개발자", model="qwen2.5:3b"
                )
                turn = await turns_repo.create(
                    session_id=practice_session.id, order_index=0, question="질문"
                )
                turn.answer = "답변"
                turn.feedback = "피드백"
                await session.commit()

                await KnowledgeChunkRepository(session).create(
                    user_id=user.id,
                    source_type="interview_practice_turn",
                    source_id=turn.id,
                    content="기존 기록",
                    embedding=[1.0, 0.0, 0.0],
                    embedding_model=settings.embedding_model,
                )
                await session.commit()

                fake = _CheckingOllamaService(engine)
                rag = RagService(session=session, ollama_service=fake, settings=settings)
                service = InterviewPracticeService(
                    session=session, ollama_service=fake, settings=settings, rag_service=rag
                )

                await service.complete_session(session_id=practice_session.id, user_id=user.id)

            return fake.checked_out_during_embed_calls
        finally:
            await engine.dispose()
            if os.path.exists(path):
                os.unlink(path)

    checked_out_during_embed_calls = asyncio.run(_run())
    # complete_session()은 index_content()를 호출하지 않으므로(submit_answer만
    # 호출한다) retrieve_relevant() 내부의 embed() 1번만 일어난다.
    assert checked_out_during_embed_calls == [1]


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
