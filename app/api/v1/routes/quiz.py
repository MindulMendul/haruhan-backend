import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user, get_ollama_service, get_rag_service
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.quiz import (
    QuizAnswerResult,
    QuizAttemptSummary,
    QuizCreateRequest,
    QuizDetailResponse,
    QuizQuestionPublic,
    QuizResponse,
    QuizResultResponse,
    QuizSubmitRequest,
    QuizUpdateRequest,
    WrongAnswerEntry,
    WrongAnswerNotebookResponse,
)
from app.services.ollama_service import OllamaService
from app.services.quiz_service import QuizService
from app.services.rag_service import RagService

router = APIRouter(prefix="/quizzes", tags=["quiz"])


def get_quiz_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
    rag_service: RagService = Depends(get_rag_service),
    settings: Settings = Depends(get_settings),
) -> QuizService:
    return QuizService(
        session=session, ollama_service=ollama_service, rag_service=rag_service, settings=settings
    )


@router.post("", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def create_quiz(
    request: Request,
    response: Response,
    payload: QuizCreateRequest,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> QuizResponse:
    # question_count는 요청 스키마의 model_validator가 None이면 기본값으로 채워둔다.
    assert payload.question_count is not None
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
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> list[QuizResponse]:
    quizzes, total = await quiz_service.list_quizzes(user_id=current_user.id, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return [QuizResponse.model_validate(q) for q in quizzes]


@router.get("/wrong-answers", response_model=WrongAnswerNotebookResponse)
async def get_wrong_answer_notebook(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> WrongAnswerNotebookResponse:
    """내가 만든 모든 퀴즈에서, 퀴즈별 최근 제출 기준으로 틀린 문제만 모아 보여준다."""
    entries, total = await quiz_service.get_wrong_answer_notebook(
        user_id=current_user.id, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return WrongAnswerNotebookResponse(
        entries=[
            WrongAnswerEntry(
                quiz_id=quiz.id,
                quiz_title=quiz.title,
                question_id=question.id,
                question_text=question.question_text,
                choices=question.choices,
                selected_index=answer.selected_index,
                correct_answer=question.correct_answer,
                explanation=question.explanation,
            )
            for quiz, question, answer in entries
        ]
    )


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


@router.patch("/{quiz_id}", response_model=QuizResponse)
async def rename_quiz(
    quiz_id: uuid.UUID,
    payload: QuizUpdateRequest,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> QuizResponse:
    quiz = await quiz_service.rename_quiz(quiz_id=quiz_id, user_id=current_user.id, title=payload.title)
    return QuizResponse.model_validate(quiz)


@router.post("/{quiz_id}/submit", response_model=QuizResultResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def submit_quiz(
    request: Request,
    response: Response,
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


@router.delete("/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quiz(
    quiz_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> None:
    await quiz_service.delete_quiz(quiz_id=quiz_id, user_id=current_user.id)


@router.get("/{quiz_id}/attempts", response_model=list[QuizAttemptSummary])
async def list_quiz_attempts(
    response: Response,
    quiz_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    quiz_service: QuizService = Depends(get_quiz_service),
) -> list[QuizAttemptSummary]:
    """이 퀴즈를 재도전한 이력을 최신순으로 보여준다 (점수 추이 확인용)."""
    attempts, total = await quiz_service.list_attempts(
        quiz_id=quiz_id, user_id=current_user.id, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return [QuizAttemptSummary.model_validate(a) for a in attempts]


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
