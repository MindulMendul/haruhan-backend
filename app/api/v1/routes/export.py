from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.export import UserDataExport
from app.services.export_service import ExportService

router = APIRouter(prefix="/export", tags=["export"])


def get_export_service(session: AsyncSession = Depends(get_db)) -> ExportService:
    return ExportService(session=session)


@router.get("/me", response_model=UserDataExport)
async def export_my_data(
    current_user: User = Depends(get_current_user),
    export_service: ExportService = Depends(get_export_service),
) -> UserDataExport:
    """내 학습챗/퀴즈/면접연습/면접복기 기록 전체를 JSON으로 내보낸다."""
    return await export_service.export_user_data(current_user.id)
