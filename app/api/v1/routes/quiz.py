import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_ollama_service
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.quiz import (
    QuizAnswerResult,
    QuizCreateRequest,
    QuizDetailResponse,
    QuizQuestionPublic,
    QuizResponse,
    QuizResultResponse,
    QuizSubmitRequest,
)
from app.services.ollama_service import OllamaService
from app.services.quiz_service import QuizService

router = APIRouter(prefix="/quizzes", tags=["quiz"])


def get_quiz_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> QuizService:
    return QuizService(session=session, ollama_service=ollama_service)


@router.post("", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def create_quiz(
    request: Request,
    payload: QuizCreateRequest,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> QuizResponse:
    quiz = await quiz_service.create_quiz(
        user_id=current_user.id,
        title=payload.title,
        study_session_id=payload.study_session_id,
        source_text=payload.source_text,
        question_count=payload.question_count,
        model=payload.model,
    )
    return QuizResponse.model_validate(quiz)


@router.get("", response_model=list[QuizResponse])
async def list_quizzes(
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> list[QuizResponse]:
    quizzes = await quiz_service.list_quizzes(user_id=current_user.id)
    return [QuizResponse.model_validate(q) for q in quizzes]


@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> QuizDetailResponse:
    quiz, questions = await quiz_service.get_quiz_with_questions(
        quiz_id=quiz_id, user_id=current_user.id
    )
    return QuizDetailResponse(
        id=quiz.id,
        title=quiz.title,
        source_study_session_id=quiz.source_study_session_id,
        created_at=quiz.created_at,
        questions=[QuizQuestionPublic.model_validate(q) for q in questions],
    )


@router.post("/{quiz_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(
    quiz_id: uuid.UUID,
    payload: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> QuizResultResponse:
    answers = [(item.question_id, item.selected_index) for item in payload.answers]
    attempt, graded = await quiz_service.submit_answers(
        quiz_id=quiz_id, user_id=current_user.id, answers=answers
    )
    return QuizResultResponse(
        attempt_id=attempt.id,
        score=attempt.score,
        total=attempt.total,
        submitted_at=attempt.submitted_at,
        answers=[
            QuizAnswerResult(
                question_id=question.id,
                selected_index=selected_index,
                is_correct=is_correct,
                correct_answer=question.correct_answer,
                explanation=question.explanation,
            )
            for question, selected_index, is_correct in graded
        ],
    )


@router.get("/{quiz_id}/result", response_model=QuizResultResponse)
async def get_quiz_result(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> QuizResultResponse:
    attempt, answer_pairs = await quiz_service.get_latest_result(
        quiz_id=quiz_id, user_id=current_user.id
    )
    return QuizResultResponse(
        attempt_id=attempt.id,
        score=attempt.score,
        total=attempt.total,
        submitted_at=attempt.submitted_at,
        answers=[
            QuizAnswerResult(
                question_id=answer.question_id,
                selected_index=answer.selected_index,
                is_correct=answer.is_correct,
                correct_answer=question.correct_answer,
                explanation=question.explanation,
            )
            for answer, question in answer_pairs
        ],
    )
