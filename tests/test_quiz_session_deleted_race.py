import asyncio
import json

from app.core.config import get_settings
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.quiz_service import QuizService
from app.services.rag_service import RagService

SAMPLE_QUIZ_JSON = json.dumps(
    {
        "questions": [
            {
                "question": "질문?",
                "choices": ["A", "B"],
                "correct_answer": "A",
                "explanation": "설명",
            }
        ]
    }
)


def test_create_quiz_from_study_session_returns_404_when_session_deleted_during_ai_call(
    db_session_factory,
):
    """create_quiz()는 학습 세션 존재를 확인한 뒤 느린 Ollama 호출(재시도 포함)을
    거쳐서야 Quiz를 만든다 - 그 사이 다른 요청이 이 세션을 지워버리면,
    source_study_session_id가 더는 존재하지 않는 부모를 가리키게 되어 Quiz
    INSERT가 IntegrityError로 실패한다(source_study_session_id는
    ondelete="SET NULL"이라 CASCADE로 지워지진 않지만, 이 INSERT 시점엔 이미
    사라진 부모를 참조하려는 것이라 여전히 위반이다). study_service.py의
    send_message/stream_message와 같은 이유로 잡지 않으면 처리되지 않은
    예외(500)가 나가버린다 - 다른 "세션 없음" 케이스와 같은 404로 변환해야
    한다. 가짜 Ollama가 퀴즈 JSON을 반환하기 "직전"에 별도 세션에서 학습
    세션을 완전히 지우도록 만들어 이 타이밍을 결정적으로 재현한다."""

    async def _run():
        async with db_session_factory() as session_a:
            settings = get_settings()
            user = await UserRepository(session_a).create_guest()
            study_session = await StudySessionRepository(session_a).create(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await StudyMessageRepository(session_a).create(
                session_id=study_session.id, role="user", content="학습 내용입니다"
            )
            await session_a.commit()

            class DeletingOllamaService:
                async def generate_json(self, prompt, model, schema):
                    async with db_session_factory() as session_b:
                        db_session = await session_b.get(type(study_session), study_session.id)
                        await session_b.delete(db_session)
                        await session_b.commit()
                    return SAMPLE_QUIZ_JSON

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            ollama = DeletingOllamaService()
            quiz_service = QuizService(
                session=session_a,
                ollama_service=ollama,
                rag_service=RagService(session=session_a, ollama_service=ollama, settings=settings),
                settings=settings,
            )

            try:
                await quiz_service.create_quiz(
                    user_id=user.id,
                    title="퀴즈",
                    study_session_id=study_session.id,
                    source_text=None,
                    question_count=1,
                    model="qwen2.5:3b",
                )
                return None
            except Exception as exc:  # noqa: BLE001 - 예외 자체를 검사해야 함
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 404
    assert exc.detail == "Study session not found"


def test_create_quiz_from_pasted_text_returns_401_when_account_deleted_during_ai_call(
    db_session_factory,
):
    """study_session_id 없이 직접 붙여넣은 소스로 만드는 퀴즈는 이 Quiz INSERT가
    참조하는 FK가 user_id(nullable=False, ondelete=CASCADE) 하나뿐이다 - 그
    사이 다른 요청이 UserService.delete_account()로 계정을 지우면 IntegrityError
    가 나는데, 원인이 될 수 있는 건 "계정이 지워졌다"뿐이다(애초에 요청에
    study_session_id 자체가 없었으니 "학습 세션이 지워졌다"는 성립할 수 없음).
    위 테스트(학습 세션 경로)와 똑같이 404 "Study session not found"로 답하면
    세션 얘기를 꺼낸 적도 없는 사용자에게 엉뚱한 오답을 주게 된다 -
    143~147라운드가 다른 서비스에 적용한 것과 같은 "계정 삭제 경쟁" 401로
    변환해야 한다. 가짜 Ollama가 퀴즈 JSON을 반환하기 "직전"에 별도 세션에서
    계정을 완전히 지우도록 만들어 이 타이밍을 결정적으로 재현한다."""

    async def _run():
        async with db_session_factory() as session_a:
            settings = get_settings()
            user = await UserRepository(session_a).create_guest()
            await session_a.commit()
            user_id = user.id

            class DeletingOllamaService:
                async def generate_json(self, prompt, model, schema):
                    async with db_session_factory() as session_b:
                        users_b = UserRepository(session_b)
                        target = await users_b.get_by_id(user_id)
                        await users_b.delete(target)
                        await session_b.commit()
                    return SAMPLE_QUIZ_JSON

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            ollama = DeletingOllamaService()
            quiz_service = QuizService(
                session=session_a,
                ollama_service=ollama,
                rag_service=RagService(session=session_a, ollama_service=ollama, settings=settings),
                settings=settings,
            )

            try:
                await quiz_service.create_quiz(
                    user_id=user_id,
                    title="퀴즈",
                    study_session_id=None,
                    source_text="직접 붙여넣은 소스입니다",
                    question_count=1,
                    model="qwen2.5:3b",
                )
                return None
            except Exception as exc:  # noqa: BLE001 - 예외 자체를 검사해야 함
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401
    assert exc.detail == {"code": "invalid_token", "message": "Could not validate credentials"}
