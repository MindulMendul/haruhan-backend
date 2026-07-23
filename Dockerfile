FROM python:3.11-slim

WORKDIR /app

# 파이썬 의존성 설치 (asyncpg는 wheel로 배포되어 별도 시스템 패키지가 필요 없음)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 복사
COPY app ./app

# 컨테이너가 탈취되어도 권한 상승이 되지 않도록 non-root 유저로 실행
RUN useradd --create-home --shell /usr/sbin/nologin appuser
USER appuser

EXPOSE 8000

# FastAPI Uvicorn 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]