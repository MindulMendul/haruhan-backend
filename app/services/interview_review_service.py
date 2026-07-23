import uuid
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.interview_review import InterviewReview
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.services.ollama_service import OllamaService, OllamaServiceError

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview review not found")
_GENERATION_FAILED = HTTPException(
    status_code=status.HTTP_502_BAD_GATEWAY, detail="피드백 생성에 실패했습니다. 다시 시도해주세요."
)


def _build_review_feedback_prompt(company: str, position: str, content: str) -> str:
    return (
        f"당신은 커리어 코치입니다. 아래는 지원자가 '{company}'의 '{position}' 직무 면접을 보고 "
        "작성한 복기(회고) 내용입니다.\n"
        f"---\n{content}\n---\n\n"
        "이 복기를 바탕으로 지원자가 잘한 점, 아쉬웠던 점, 다음 면접을 위한 구체적인 개선 제안을 "
        "작성해주세요."
    )


class InterviewReviewService:
    def __init__(self, session: AsyncSession, ollama_service: OllamaService) -> None:
        self._session = session
        self._reviews = InterviewReviewRepository(session)
        self._ollama = ollama_service

    async def create_review(
        self,
        user_id: uuid.UUID,
        company: str,
        position: str,
        interview_date: date,
        content: str,
        model: str,
    ) -> InterviewReview:
        feedback = await self._generate_feedback(company, position, content, model)

        review = await self._reviews.create(
            user_id=user_id,
            company=company,
            position=position,
            interview_date=interview_date,
            content=content,
            model=model,
        )
        review.ai_feedback = feedback
        await self._session.commit()
        return review

    async def list_reviews(self, user_id: uuid.UUID) -> list[InterviewReview]:
        return await self._reviews.list_for_user(user_id)

    async def get_review(self, review_id: uuid.UUID, user_id: uuid.UUID) -> InterviewReview:
        review = await self._reviews.get_for_user(review_id, user_id)
        if review is None:
            raise _NOT_FOUND
        return review

    async def update_review(
        self,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        company: str | None,
        position: str | None,
        interview_date: date | None,
        content: str | None,
    ) -> InterviewReview:
        review = await self._reviews.get_for_user(review_id, user_id)
        if review is None:
            raise _NOT_FOUND

        if company is not None:
            review.company = company
        if position is not None:
            review.position = position
        if interview_date is not None:
            review.interview_date = interview_date

        # 정답/피드백은 content에 의존하므로, content가 실제로 바뀔 때만 다시 생성한다.
        if content is not None and content != review.content:
            feedback = await self._generate_feedback(review.company, review.position, content, review.model)
            review.content = content
            review.ai_feedback = feedback

        await self._session.commit()
        return review

    async def delete_review(self, review_id: uuid.UUID, user_id: uuid.UUID) -> None:
        review = await self._reviews.get_for_user(review_id, user_id)
        if review is None:
            raise _NOT_FOUND
        await self._reviews.delete(review)
        await self._session.commit()

    async def _generate_feedback(self, company: str, position: str, content: str, model: str) -> str:
        prompt = _build_review_feedback_prompt(company, position, content)
        try:
            return await self._ollama.chat(messages=[{"role": "user", "content": prompt}], model=model)
        except OllamaServiceError as exc:
            raise _GENERATION_FAILED from exc
