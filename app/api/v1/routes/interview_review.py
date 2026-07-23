import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_ollama_service
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.interview_review import (
    InterviewReviewCreateRequest,
    InterviewReviewResponse,
    InterviewReviewUpdateRequest,
)
from app.services.interview_review_service import InterviewReviewService
from app.services.ollama_service import OllamaService

router = APIRouter(prefix="/interview/reviews", tags=["interview-review"])


def get_interview_review_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> InterviewReviewService:
    return InterviewReviewService(session=session, ollama_service=ollama_service)


@router.post("", response_model=InterviewReviewResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def create_review(
    request: Request,
    payload: InterviewReviewCreateRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> InterviewReviewResponse:
    review = await service.create_review(
        user_id=current_user.id,
        company=payload.company,
        position=payload.position,
        interview_date=payload.interview_date,
        content=payload.content,
        model=payload.model,
    )
    return InterviewReviewResponse.model_validate(review)


@router.get("", response_model=list[InterviewReviewResponse])
async def list_reviews(
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> list[InterviewReviewResponse]:
    reviews = await service.list_reviews(user_id=current_user.id)
    return [InterviewReviewResponse.model_validate(r) for r in reviews]


@router.get("/{review_id}", response_model=InterviewReviewResponse)
async def get_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> InterviewReviewResponse:
    review = await service.get_review(review_id=review_id, user_id=current_user.id)
    return InterviewReviewResponse.model_validate(review)


@router.patch("/{review_id}", response_model=InterviewReviewResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def update_review(
    request: Request,
    review_id: uuid.UUID,
    payload: InterviewReviewUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> InterviewReviewResponse:
    review = await service.update_review(
        review_id=review_id,
        user_id=current_user.id,
        company=payload.company,
        position=payload.position,
        interview_date=payload.interview_date,
        content=payload.content,
    )
    return InterviewReviewResponse.model_validate(review)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> None:
    await service.delete_review(review_id=review_id, user_id=current_user.id)
