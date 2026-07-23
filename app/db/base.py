from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # INSERT 직후 서버 사이드 기본값(created_at 등)을 항상 즉시 채워온다.
    # 이게 없으면 커밋 후 동기 코드(Pydantic 직렬화 등)에서 그 속성에 처음 접근할 때
    # SQLAlchemy가 지연 로드를 시도하다 MissingGreenlet 에러가 난다.
    __mapper_args__ = {"eager_defaults": True}
