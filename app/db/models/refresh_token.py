import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 원문 토큰은 저장하지 않고 SHA-256 해시만 저장한다 (DB 유출 시에도 토큰 재사용 불가).
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # 아래 두 시각 컬럼은 tz 없이 UTC 기준 naive datetime으로 통일해서 다룬다 (app.core.tokens.utcnow_naive).
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
