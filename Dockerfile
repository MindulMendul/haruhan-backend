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
#
# --ws-max-size=1048576: HTTP 요청은 MaxBodySizeMiddleware(기본 1MiB,
# MAX_BODY_SIZE_BYTES)로 크기를 막아두지만, WebSocket 경로(study/interview-review
# 스트리밍)는 이 미들웨어를 안 거치고 uvicorn의 기본값(16MiB)을 그대로 쓰고
# 있었다 - 아무도 의도적으로 정한 적 없는 값인데, 정작 실제 메시지 크기
# 기대치(max_prompt_length=4000자, max_review_content_length=10000자)보다
# 수백 배 더 관대해서 WS 쪽만 유독 대용량 메시지를 통한 메모리 소모형 DoS에
# 취약했다. 직접 uvicorn 서버를 띄워 2MiB 메시지가 기본값으로는 그대로
# 통과하고 이 플래그를 켜면 프로토콜 레벨에서 거부되는(1009 message too big)
# 것까지 재현 확인했다. HTTP 쪽 기본값과 같은 1MiB로 맞춰서 두 경로의
# 보호 수준을 통일한다.
#
# --log-level warning: 학습챗/면접복기 스트리밍 WebSocket 인증(get_current_user_ws,
# core/dependencies.py)은 브라우저가 커스텀 헤더를 못 보내서 access token을
# 쿼리 파라미터(?token=<access_token>)로 받는다(FRONTEND_INTEGRATION.md에 문서화된
# 정상 계약). uvicorn의 기본(info) 로그 레벨에서는 이 핸드셰이크마다
# "uvicorn.error" 로거(핸드셰이크/연결 자체를 다루는 websockets_sansio_impl.py가
# 씀 - "uvicorn.access"가 아니라서 173라운드의 own AccessLogMiddleware/WS 접근
# 로그와는 완전히 별개 경로)가 `127.0.0.1:PORT - "WebSocket /.../stream?token=
# <JWT 전체>" [accepted]`를 그대로 stdout에 찍는다 - docker-compose.yml의
# json-file 로그(141라운드, 최대 30MB 보관)에 최대 access_token_expire_minutes
# (기본 30분)간 유효한 실제 access token이 평문으로 계속 쌓인다. 직접 uvicorn을
# 띄워 실제 JWT가 이 로그 줄에 그대로 찍히는 것과, --no-access-log(=uvicorn.access
# 로거만 끔)는 이 줄에 전혀 영향이 없지만(다른 로거라서) 로그 레벨을 warning으로
# 올리면 uvicorn 자신의 이 INFO 레벨 핸드셰이크/기동 로그가 전부 사라지는 것까지
# 재현 확인했다. HTTP 요청/WS 연결 각각의 access 로그는 이미 haruhan.access
# 로거(14/173라운드)가 쿼리 없이 완전히 대체하고 있어서 정보 손실이 없다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*", "--ws-max-size=1048576", "--log-level", "warning"]