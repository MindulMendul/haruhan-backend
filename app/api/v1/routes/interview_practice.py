import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user, get_ollama_service
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.interview_practice import (
    InterviewPracticeAnswerRequest,
    InterviewPracticeAnswerResponse,
    InterviewPracticeCreateRequest,
    InterviewPracticeSessionDetailResponse,
    InterviewPracticeSessionResponse,
    InterviewPracticeTurnResponse,
)
from app.services.interview_practice_service import InterviewPracticeService
from app.services.ollama_service import OllamaService

router = APIRouter(prefix="/interview/practice-sessions", tags=["interview-practice"])


def get_interview_practice_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
    settings: Settings = Depends(get_settings),
) -> InterviewPracticeService:
    return InterviewPracticeService(session=session, ollama_service=ollama_service, settings=settings)


@router.post("", response_model=InterviewPracticeSessionDetailResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def create_session(
    request: Request,
    payload: InterviewPracticeCreateRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewPracticeService = Depends(get_interview_practice_service),
) -> InterviewPracticeSessionDetailResponse:
    practice_session, first_turn = await service.create_session(
        user_id=current_user.id, topic=payload.topic, model=payload.model
    )
    return InterviewPracticeSessionDetailResponse(
        id=practice_session.id,
        topic=practice_session.topic,
        model=practice_session.model,
        status=practice_session.status,
        overall_feedback=practice_session.overall_feedback,
        created_at=practice_session.created_at,
        updated_at=practice_session.updated_at,
        turns=[InterviewPracticeTurnResponse.model_validate(first_turn)],
    )


@router.get("", response_model=list[InterviewPracticeSessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    service: InterviewPracticeService = Depends(get_interview_practice_service),
) -> list[InterviewPracticeSessionResponse]:
    sessions = await service.list_sessions(user_id=current_user.id)
    return [InterviewPracticeSessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=InterviewPracticeSessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewPracticeService = Depends(get_interview_practice_service),
) -> InterviewPracticeSessionDetailResponse:
    practice_session, turns = await service.get_session_with_turns(
        session_id=session_id, user_id=current_user.id
    )
    return InterviewPracticeSessionDetailResponse(
        id=practice_session.id,
        topic=practice_session.topic,
        model=practice_session.model,
        status=practice_session.status,
        overall_feedback=practice_session.overall_feedback,
        created_at=practice_session.created_at,
        updated_at=practice_session.updated_at,
        turns=[InterviewPracticeTurnResponse.model_validate(t) for t in turns],
    )


@router.post("/{session_id}/answers", response_model=InterviewPracticeAnswerResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def submit_answer(
    request: Request,
    session_id: uuid.UUID,
    payload: InterviewPracticeAnswerRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewPracticeService = Depends(get_interview_practice_service),
) -> InterviewPracticeAnswerResponse:
    answered_turn, next_turn = await service.submit_answer(
        session_id=session_id, user_id=current_user.id, answer=payload.answer
    )
    return InterviewPracticeAnswerResponse(
        answered_turn=InterviewPracticeTurnResponse.model_validate(answered_turn),
        next_turn=InterviewPracticeTurnResponse.model_validate(next_turn) if next_turn else None,
    )


@router.post("/{session_id}/complete", response_model=InterviewPracticeSessionResponse)
async def complete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewPracticeService = Depends(get_interview_practice_service),
) -> InterviewPracticeSessionResponse:
    practice_session = await service.complete_session(session_id=session_id, user_id=current_user.id)
    return InterviewPracticeSessionResponse.model_validate(practice_session)
