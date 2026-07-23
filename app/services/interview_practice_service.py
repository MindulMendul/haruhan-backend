import json
import uuid

from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.interview_practice_session import InterviewPracticeSession
from app.db.models.interview_practice_turn import InterviewPracticeTurn
from app.repositories.interview_practice_repository import (
    InterviewPracticeSessionRepository,
    InterviewPracticeTurnRepository,
)
from app.services.ollama_service import OllamaService, OllamaServiceError

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview practice session not found")
_ALREADY_FINISHED = HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 종료된 면접 연습입니다.")
_NO_PENDING_QUESTION = HTTPException(status_code=status.HTTP_409_CONFLICT, detail="답변할 질문이 없습니다.")
_GENERATION_FAILED = HTTPException(
    status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 응답 생성에 실패했습니다. 다시 시도해주세요."
)


class _FeedbackWithNextQuestion(BaseModel):
    feedback: str
    next_question: str


_FEEDBACK_NEXT_QUESTION_SCHEMA = _FeedbackWithNextQuestion.model_json_schema()


def _build_first_question_prompt(topic: str) -> str:
    return (
        f"당신은 '{topic}' 직무를 채용하는 면접관입니다. 지원자에게 던질 첫 번째 면접 질문을 "
        "한국어로 하나만 작성해주세요. 질문 내용만 출력하고 다른 설명은 붙이지 마세요."
    )


def _build_feedback_and_next_question_prompt(
    topic: str, history: list[tuple[str, str]], question: str, answer: str
) -> str:
    history_text = "\n".join(f"Q: {q}\nA: {a}" for q, a in history)
    return (
        f"당신은 '{topic}' 직무 면접관입니다. 아래는 지금까지의 면접 대화입니다.\n"
        f"{history_text}\n"
        f"마지막 질문: {question}\n"
        f"지원자의 답변: {answer}\n\n"
        "위 답변에 대한 건설적인 피드백(feedback)과, 앞의 대화와 겹치지 않는 다음 면접 질문"
        "(next_question)을 JSON으로 작성해주세요."
    )


def _build_final_feedback_prompt(topic: str, question: str, answer: str) -> str:
    return (
        f"당신은 '{topic}' 직무 면접관입니다.\n"
        f"질문: {question}\n"
        f"지원자의 답변: {answer}\n\n"
        "이 답변에 대한 건설적인 피드백만 작성해주세요. 새로운 질문은 하지 마세요."
    )


def _build_overall_feedback_prompt(topic: str, qa_pairs: list[tuple[str, str, str]]) -> str:
    transcript = "\n\n".join(f"Q: {q}\nA: {a}\n피드백: {f}" for q, a, f in qa_pairs)
    return (
        f"당신은 '{topic}' 직무 면접관입니다. 아래는 방금 끝난 모의 면접의 전체 기록입니다.\n\n"
        f"{transcript}\n\n"
        "지원자의 전반적인 강점과 개선점을 종합한 총평을 작성해주세요."
    )


class InterviewPracticeService:
    def __init__(self, session: AsyncSession, ollama_service: OllamaService, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._sessions = InterviewPracticeSessionRepository(session)
        self._turns = InterviewPracticeTurnRepository(session)
        self._ollama = ollama_service

    async def create_session(
        self, user_id: uuid.UUID, topic: str, model: str
    ) -> tuple[InterviewPracticeSession, InterviewPracticeTurn]:
        try:
            first_question = await self._ollama.generate(
                prompt=_build_first_question_prompt(topic), model=model
            )
        except OllamaServiceError as exc:
            raise _GENERATION_FAILED from exc

        practice_session = await self._sessions.create(user_id=user_id, topic=topic, model=model)
        first_turn = await self._turns.create(
            session_id=practice_session.id, order_index=0, question=first_question
        )
        await self._session.commit()
        return practice_session, first_turn

    async def list_sessions(self, user_id: uuid.UUID) -> list[InterviewPracticeSession]:
        return await self._sessions.list_for_user(user_id)

    async def get_session_with_turns(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[InterviewPracticeSession, list[InterviewPracticeTurn]]:
        practice_session = await self._sessions.get_for_user(session_id, user_id)
        if practice_session is None:
            raise _NOT_FOUND
        turns = await self._turns.list_for_session(session_id)
        return practice_session, turns

    async def submit_answer(
        self, session_id: uuid.UUID, user_id: uuid.UUID, answer: str
    ) -> tuple[InterviewPracticeTurn, InterviewPracticeTurn | None]:
        practice_session = await self._sessions.get_for_user(session_id, user_id)
        if practice_session is None:
            raise _NOT_FOUND
        if practice_session.status != "in_progress":
            raise _ALREADY_FINISHED

        turns = await self._turns.list_for_session(session_id)
        current_turn = turns[-1] if turns else None
        if current_turn is None or current_turn.answer is not None:
            raise _NO_PENDING_QUESTION

        # 답변을 먼저 커밋하지 않고 AI 호출까지 한 트랜잭션으로 묶는다: AI 호출이 실패하면
        # 답변 자체도 롤백되어 current_turn이 다시 "미답변" 상태로 남고, 그대로 재시도하면 된다
        # (study_service의 메시지 저장과 달리, 여기서는 반쯤 처리된 상태로 멈추는 것을 피하기 위함).
        history = [(t.question, t.answer) for t in turns[:-1] if t.answer is not None]

        next_turn: InterviewPracticeTurn | None
        if len(turns) < self._settings.max_interview_questions:
            prompt = _build_feedback_and_next_question_prompt(
                practice_session.topic, history, current_turn.question, answer
            )
            try:
                raw = await self._ollama.generate_json(
                    prompt=prompt, model=practice_session.model, schema=_FEEDBACK_NEXT_QUESTION_SCHEMA
                )
                parsed = _FeedbackWithNextQuestion.model_validate_json(raw)
            except (OllamaServiceError, ValidationError, json.JSONDecodeError) as exc:
                raise _GENERATION_FAILED from exc

            current_turn.answer = answer
            current_turn.feedback = parsed.feedback
            next_turn = await self._turns.create(
                session_id=session_id, order_index=len(turns), question=parsed.next_question
            )
        else:
            prompt = _build_final_feedback_prompt(practice_session.topic, current_turn.question, answer)
            try:
                feedback = await self._ollama.chat(
                    messages=[{"role": "user", "content": prompt}], model=practice_session.model
                )
            except OllamaServiceError as exc:
                raise _GENERATION_FAILED from exc

            current_turn.answer = answer
            current_turn.feedback = feedback
            next_turn = None

        await self._sessions.touch(practice_session)
        await self._session.commit()
        return current_turn, next_turn

    async def complete_session(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> InterviewPracticeSession:
        practice_session = await self._sessions.get_for_user(session_id, user_id)
        if practice_session is None:
            raise _NOT_FOUND
        if practice_session.status != "in_progress":
            raise _ALREADY_FINISHED

        turns = await self._turns.list_for_session(session_id)
        answered_turns = [t for t in turns if t.answer is not None and t.feedback is not None]
        if not answered_turns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="답변한 질문이 없어 종합 피드백을 생성할 수 없습니다.",
            )

        prompt = _build_overall_feedback_prompt(
            practice_session.topic, [(t.question, t.answer, t.feedback) for t in answered_turns]
        )
        try:
            overall_feedback = await self._ollama.chat(
                messages=[{"role": "user", "content": prompt}], model=practice_session.model
            )
        except OllamaServiceError as exc:
            raise _GENERATION_FAILED from exc

        practice_session.status = "completed"
        practice_session.overall_feedback = overall_feedback
        await self._sessions.touch(practice_session)
        await self._session.commit()
        return practice_session
