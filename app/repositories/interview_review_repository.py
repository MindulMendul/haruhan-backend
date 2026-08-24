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
        # interview_date는 하루 단위 정밀도의 사용자 입력값이라, 같은 날짜로 등록한
        # 복기가 여러 개면(예: 하루에 여러 면접을 본 경우) 동률이 실제로 흔하다.
        # 2차 정렬 기준이 없으면 동률 사이의 순서가 SQL 표준상 정의되어 있지 않아,
        # 페이지마다 그 순서가 달라져 LIMIT/OFFSET으로 나눠 받을 때 같은 복기가
        # 두 페이지에 다시 나오거나(중복) 어느 페이지에도 안 나올(누락) 수 있다.
        # id를 2차 정렬 기준으로 추가해 동률을 항상 같은 순서로 결정론적으로 깨지도록 한다.
        result = await self._session.execute(
            select(InterviewReview)
            .where(InterviewReview.user_id == user_id)
            .order_by(InterviewReview.interview_date.desc(), InterviewReview.id.desc())
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
