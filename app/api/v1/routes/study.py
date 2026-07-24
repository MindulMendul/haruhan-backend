import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_ollama_service, get_rag_service
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.study import (
    StudyMessageCreateRequest,
    StudyMessageCreateResponse,
    StudyMessageResponse,
    StudySessionCreateRequest,
    StudySessionDetailResponse,
    StudySessionResponse,
)
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService
from app.services.study_service import StudyService

router = APIRouter(prefix="/study/sessions", tags=["study"])


def get_study_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
    rag_service: RagService = Depends(get_rag_service),
) -> StudyService:
    return StudyService(session=session, ollama_service=ollama_service, rag_service=rag_service)


@router.post("", response_model=StudySessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: StudySessionCreateRequest,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> StudySessionResponse:
    study_session = await study_service.create_session(
        user_id=current_user.id, title=payload.title, model=payload.model
    )
    return StudySessionResponse.model_validate(study_session)


@router.get("", response_model=list[StudySessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> list[StudySessionResponse]:
    sessions = await study_service.list_sessions(user_id=current_user.id)
    return [StudySessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=StudySessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> StudySessionDetailResponse:
    study_session, messages = await study_service.get_session_with_messages(
        session_id=session_id, user_id=current_user.id
    )
    return StudySessionDetailResponse(
        id=study_session.id,
        title=study_session.title,
        model=study_session.model,
        created_at=study_session.created_at,
        updated_at=study_session.updated_at,
        messages=[StudyMessageResponse.model_validate(m) for m in messages],
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> None:
    await study_service.delete_session(session_id=session_id, user_id=current_user.id)


@router.post("/{session_id}/messages", response_model=StudyMessageCreateResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def send_message(
    request: Request,
    session_id: uuid.UUID,
    payload: StudyMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> StudyMessageCreateResponse:
    user_message, assistant_message = await study_service.send_message(
        session_id=session_id, user_id=current_user.id, content=payload.content
    )
    return StudyMessageCreateResponse(
        user_message=StudyMessageResponse.model_validate(user_message),
        assistant_message=StudyMessageResponse.model_validate(assistant_message),
    )
