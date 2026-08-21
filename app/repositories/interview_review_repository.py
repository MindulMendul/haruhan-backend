import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.interview_review import InterviewReview


class InterviewReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        company: str,
        position: str,
        interview_date: date,
        content: str,
        model: str,
    ) -> InterviewReview:
        review = InterviewReview(
            user_id=user_id,
            company=company,
            position=position,
            interview_date=interview_date,
            content=content,
            model=model,
        )
        self._session.add(review)
        await self._session.flush()
        return review

    async def list_for_user(self, user_id: uuid.UUID, limit: int, offset: int) -> list[InterviewReview]:
        result = await self._session.execute(
            select(InterviewReview)
            .where(InterviewReview.user_id == user_id)
            .order_by(InterviewReview.interview_date.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[InterviewReview]:
        """페이지네이션 없이 전체를 가져온다 - 데이터 export처럼 전량이 필요할 때 쓴다."""
        result = await self._session.execute(
            select(InterviewReview)
            .where(InterviewReview.user_id == user_id)
            .order_by(InterviewReview.created_at)
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(InterviewReview).where(InterviewReview.user_id == user_id)
        )
        return result.scalar_one()

    async def get_for_user(self, review_id: uuid.UUID, user_id: uuid.UUID) -> InterviewReview | None:
        result = await self._session.execute(
            select(InterviewReview).where(
                InterviewReview.id == review_id, InterviewReview.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, review: InterviewReview) -> None:
        await self._session.delete(review)
        await self._session.flush()
