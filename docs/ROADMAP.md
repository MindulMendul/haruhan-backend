# 로드맵

하네스 루프(Claude Code Remote Routine)가 이 리스트를 백로그로 참고해서, 매 사이클마다
다음 미완료 항목을 하나 골라 구현한다. 완료하면 체크하고 커밋/push 한다 — 기존 PR(#5)에
그대로 반영되며, **PR 머지는 사람이 직접 한다** (이 루프는 push까지만 자동으로 함).

## 진행 방식 (루프가 따를 규칙)

- 레이어드 아키텍처(`app/{core,api,services,repositories,schemas,db}`) 컨벤션을 따른다.
- DB 스키마가 바뀌면 Alembic 마이그레이션을 만들고, SQLite로 upgrade → 스키마 확인 →
  `alembic check`(드리프트 없음) → downgrade 검증까지 마친다.
- 새/변경된 코드는 반드시 테스트를 추가하고 전체 회귀(`pytest`)를 통과시킨다.
- LLM에 사용자 입력을 프롬프트로 꽂는 곳은 `[섹션]` 라벨 + injection 방지 문구 패턴을 따른다.
- 각 항목 완료 시: 체크박스 갱신 + 커밋 + `claude/fastapi-architecture-improvements-pax3xs`
  브랜치에 push. 새 PR을 만들지 않는다 (기존 PR #5에 자동으로 반영됨).
- 진짜 설계 판단이 필요한 모호한 지점이 있으면, 기존 코드베이스의 가장 비슷한 패턴을
  따르고 커밋 메시지/보고에 그 판단 근거를 남긴다.
- 되돌리기 힘든 파괴적 작업(강제 push, 실서비스 DB 대상 마이그레이션 downgrade, 브랜치
  삭제 등)은 하지 않는다.
- 백로그가 전부 체크된 상태로 사이클이 시작되면, "할 일 없음"으로 끝내지 말고 코드베이스를
  다시 훑어 새로 가치 있는 개선 항목을 몇 개 찾아 백로그에 추가한 뒤(새 라운드 섹션으로),
  그중 하나를 그 사이클 안에서 바로 구현까지 마친다.

## 백로그

- [x] 1. 면접연습(interview practice)에도 RAG 그라운딩 확장 — 학습챗에만 있는 RAG를
      면접연습 질문/피드백에도 적용, 사용자의 과거 학습/복기 내용을 참고하게 함
- [x] 2. 게스트 → 실계정 전환(계정 연결) API — 게스트로 쌓은 데이터를 유지한 채
      email/password를 등록해 실계정으로 승격
- [x] 3. 학습챗 세션 / 면접복기 목록 페이지네이션
- [x] 4. RagService 색인 실패 로깅 추가 (지금은 조용히 무시함)
- [x] 5. 만료된 refresh token 정리 스케줄러 job 추가 (APScheduler)
- [x] 6. Redis 레이트리밋 실제 전환 (구조는 있음, 연결만 안 되어 있음)
- [x] 7. 429 응답에 Retry-After 헤더 추가
- [x] 8. 퀴즈 생성 JSON 파싱 실패 시 자동 재시도 (1회)
- [x] 9. CI에 타입체크(mypy) 도입
- [x] 10. pytest-cov 커버리지 리포트 기반으로 빈 테스트 케이스 보강

## 백로그 (2라운드)

- [x] 11. 학습챗 응답 스트리밍 (WebSocket) — 지금은 Ollama 응답이 다 끝나야
      한 번에 반환됨. WebSocket 엔드포인트를 새로 열어 토큰 단위로 스트리밍.
      기존 REST `POST /study/sessions/{id}/messages`는 그대로 유지하고
      스트리밍은 별도 경로로 추가 (하위호환). Ollama `/api/chat`을
      `stream: true`로 호출해 청크를 그대로 클라이언트에 릴레이하면 됨.
- [x] 12. Ollama 모델 목록 조회 API — 프론트가 모델명을 하드코딩하지 않고
      서버가 실제로 쓸 수 있는 모델 목록을 알려줌 (Ollama `/api/tags` 프록시).
      인증 필요 없는 공개 엔드포인트로 무방.
- [x] 13. 퀴즈 오답노트 — 사용자가 틀린 문제만 모아서 다시 볼 수 있는 조회
      엔드포인트. 기존 QuizAnswer(is_correct)를 사용자 전체 퀴즈에 걸쳐
      집계하면 됨, 새 테이블 불필요할 가능성이 높음 - 먼저 확인할 것.
- [x] 14. 구조화된 액세스 로그 미들웨어 — 지금은 처리되지 않은 예외만
      로깅됨. 정상 요청도 method/path/status/처리시간/user_id(있으면)를
      구조화된 형태로 로깅.
- [x] 15. RAG 백필 스크립트 스케줄러 자동화 — `scripts/backfill_knowledge_chunks.py`가
      지금은 수동 실행 스크립트로만 존재. 색인 실패했던 항목을 주기적으로
      재시도하는 용도로 스케줄러 job화 (매번 전체를 다시 긁는 게 아니라,
      아직 색인 안 된 것만 대상으로 하는 방식 고민할 것).
- [x] 16. 데이터 export(JSON) — 사용자가 자기 학습챗/퀴즈/면접 기록을
      JSON으로 내보낼 수 있는 엔드포인트. PDF는 이번 라운드 범위 밖(별도
      라이브러리 의존성 검토 필요) - JSON만.
- [x] 17. Prometheus 메트릭 + Grafana — FastAPI에 `/metrics` 엔드포인트를
      노출(요청 수/지연시간/상태코드 등 기본 메트릭 + 가능하면 회원가입/게스트
      전환/퀴즈 생성 같은 비즈니스 카운터 몇 개). docker-compose에 prometheus,
      grafana 서비스 추가하고 prometheus가 haruhan-backend의 /metrics를
      스크레이프하도록 설정. Grafana는 Prometheus 데이터소스만 미리
      프로비저닝해두고, 대시보드 패널 구성까지는 이번 범위 밖(사람이 나중에
      직접 만듦) - 데이터소스 연결까지만 자동화.

## 백로그 (3라운드)

- [x] 18. `/health/ready`에 Redis/Ollama 상태 포함 — 지금은 DB 연결만 확인함.
      레이트리밋을 떠받치는 Redis, 모든 LLM 기능의 기반인 Ollama 중 하나라도
      응답이 없으면 함께 unavailable(503) 처리할 것. 응답 바디에 의존성별
      상태를 구분해서 넣어(예: `{"database": "connected", "redis": "...",
      "ollama": "..."}`) 어떤 게 죽었는지 바로 알 수 있게 할 것.
- [x] 19. Refresh token 재사용 탐지 — 지금은 단순 rotation만 있고(사용된
      토큰은 즉시 폐기 후 새로 발급), 이미 폐기된 토큰이 다시 제시됐을 때
      탈취 의심 신호로 보는 로직이 없음. 폐기된 토큰이 재사용되면 해당
      사용자의 모든 refresh token을 즉시 전부 폐기(전체 세션 강제 로그아웃)할
      것 - RefreshTokenRepository에 "유저의 모든 토큰 폐기" 메서드 추가 필요.
- [x] 20. Ollama 모델 목록 응답 캐싱 — `/api/v1/models`가 요청마다 Ollama
      `/api/tags`를 직접 호출함. 짧은 TTL(예: 60초) 캐시를 둬서 반복 호출을
      줄일 것. Redis가 연결돼 있으면 Redis TTL 캐시, 없으면 인메모리 TTL
      캐시로 폴백하는 방식 고려할 것.
- [x] 21. 구조화된 에러 응답 포맷 — 지금은 FastAPI 기본 `{"detail": "..."}`
      뿐이라 프론트가 에러 종류를 한글 메시지 문자열로 구분해야 함.
      `{"error": {"code": "...", "message": "..."}}` 같은 일관된 스키마로
      전환. 범위가 크므로 전역 예외 핸들러(HTTPException, 요청 검증 오류,
      미처리 예외)부터 통일하고, 기존 라우트/서비스의 HTTPException 호출부는
      점진적으로 code를 붙이는 방식으로 접근할 것 - 한 번에 전체를 바꾸려
      들지 말 것.
- [x] 22. 퀴즈 제출 중복/멱등성 처리 — 네트워크 재시도 등으로 같은 제출이
      중복 채점(QuizAttempt가 여러 개 생성)되는 걸 막을 장치가 없음. 가장
      간단한 접근(예: 아주 짧은 시간 내 동일 조합 재제출이면 새로 채점하지
      않고 직전 결과를 그대로 반환)부터 검토할 것 - Idempotency-Key 헤더
      방식까지 갈지는 설계 판단이 필요하니 기존 코드베이스 패턴에 맞는 쪽으로
      정하고 근거를 남길 것.
- [x] 23. 퀴즈 콘텐츠 RAG 색인 대상 포함 검토 — 학습챗 메시지/면접연습
      턴/면접복기는 전부 RAG 색인되는데 퀴즈(문제/오답)만 빠져 있음. 의도적
      제외인지(퀴즈는 이미 색인된 학습챗 내용에서 파생되니 중복이라서) 먼저
      확인하고, 필요하다고 판단되면 퀴즈 생성/제출 시점에 `index_content()`
      훅을 추가할 것.

## 백로그 (4라운드)

- [x] 24. 계정 삭제(회원 탈퇴) API — JSON export(`/api/v1/export/me`)는
      있는데 대칭되는 "내 계정 + 관련 데이터 전체 삭제"는 없음. `DELETE
      /api/v1/users/me` 추가. CASCADE 제약이 이미 대부분의 테이블에 걸려
      있으니(FK ondelete="CASCADE") User 로우만 지우면 나머지가 따라
      지워지는지 먼저 확인하고, 그렇지 않은 관계가 있으면 명시적으로 정리할
      것. 삭제 전 확인(비밀번호 재입력 등) 필요 여부는 기존 UserService
      패턴(update_profile의 current_password 검증)에 맞춰 판단할 것.
- [x] 25. docker-compose 헬스체크 — haruhan-backend/redis/prometheus/grafana
      전부 `healthcheck:` 블록이 없음. 각 서비스에 적절한 healthcheck(예:
      haruhan-backend는 `GET /health`, redis는 `redis-cli ping`)를 추가하고,
      `depends_on`을 `condition: service_healthy`로 바꿔서 실제로 뜬 뒤에만
      의존 서비스가 시작하게 할 것.
- [x] 26. CI 커버리지 게이트 — `.github/workflows/ci.yml`의 `pytest --cov=app`가
      커버리지를 리포트만 하고 강제하지 않음. `--cov-fail-under=N`을 추가해서
      회귀가 커버리지를 깎으면 CI가 실패하게 할 것. N은 현재 실제 커버리지보다
      살짝 낮게 잡아서(예: 현재 95%대라면 90) 사소한 변동에 CI가 계속
      깨지지 않게 여유를 둘 것.

## 백로그 (5라운드)

- [x] 27. 학습챗 WebSocket 스트리밍에 레이트리밋 적용 — WS 스트리밍 라우트
      (`/study/sessions/{id}/stream`) 도입 당시(11번 항목) "slowapi가 HTTP
      전용이라 후속 과제"로 문서에 명시해둔 채 방치돼 있었음(FRONTEND_INTEGRATION.md에
      경고 문구까지 있었음). REST의 `@limiter.limit(chat_rate_limit)`과 같은
      한도를 메시지 단위로 수동 적용할 것 - slowapi의 `Limiter.limit()` 데코레이터는
      HTTP 요청/응답 사이클 전용이라 WS에는 못 붙이므로, 같은 storage를 공유하는
      저수준 API(`limiter.limiter.hit()`)로 직접 체크할 것.
- [ ] 28. 데이터 export PDF 옵션 — JSON export(`/api/v1/export/me`)는 있는데
      PDF는 16번 항목에서 "별도 라이브러리 의존성 검토 필요"로 범위 밖에
      뺐었음. 가벼운 라이브러리(예: weasyprint, fpdf2 등) 검토 후 추가할지,
      아니면 계속 범위 밖으로 둘지부터 판단하고 근거를 남길 것 - 새 무거운
      네이티브 의존성(weasyprint는 시스템 라이브러리 필요)을 들이는 비용 대비
      가치가 있는지 먼저 따져볼 것.
- [ ] 29. 면접연습/면접복기에도 WebSocket 스트리밍 확장 검토 — 학습챗만
      WebSocket 스트리밍이 있고, 면접연습 답변 피드백/면접복기 AI 피드백
      생성은 여전히 동기 REST라 전체 응답이 끝날 때까지 블로킹됨. 학습챗과
      같은 패턴(기존 REST 유지 + 별도 스트리밍 경로 추가)으로 확장할
      가치가 있는지 판단할 것 - 사용자가 실시간으로 지켜볼 만큼 응답이
      긴 케이스인지 먼저 확인할 것.
