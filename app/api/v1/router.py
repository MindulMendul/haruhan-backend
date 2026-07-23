from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    chat,
    health,
    interview_practice,
    interview_review,
    quiz,
    study,
    users,
)

# 헬스체크는 버전 없이 루트에 둔다 (k8s/로드밸런서 probe 관례).
api_router = APIRouter()
api_router.include_router(health.router)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth.router)
v1_router.include_router(users.router)
v1_router.include_router(chat.router)
v1_router.include_router(study.router)
v1_router.include_router(quiz.router)
v1_router.include_router(interview_practice.router)
v1_router.include_router(interview_review.router)

api_router.include_router(v1_router)
