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
#
# --proxy-headers --forwarded-allow-ips="*": docker-compose 구성상 이 컨테이너는
# 호스트에 포트를 노출하지 않고 Caddy 리버스 프록시를 통해서만 트래픽을 받는다
# (docker-compose.yml 참고 - haruhan-backend에는 ports: 매핑이 없음). 이 플래그
# 없이는 uvicorn이 Caddy가 보내는 X-Forwarded-For를 신뢰하지 않아 모든 요청의
# request.client.host가 Caddy 컨테이너 IP로 찍혀서, IP 기준 레이트리밋
# (auth_rate_limit/chat_rate_limit)이 실제로는 전체 사용자가 하나의 버킷을
# 공유하는 것과 같아져 버린다(한 사용자가 다른 모든 사용자를 429로 몰아넣을 수
# 있음) - 접근 로그의 client IP도 마찬가지로 의미가 없어진다. "*"를 쓰는 게
# 안전한 이유는 백엔드 포트 자체가 외부에 노출되지 않아 Caddy를 거치지 않고
# 직접 접속해 헤더를 위조할 방법이 없기 때문이다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]