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
- [x] 28. 데이터 export PDF 옵션 — 검토 결과 **범위 밖으로 계속 둠**.
      fpdf2(순수 파이썬, 무거운 네이티브 의존성 없음)로 실제 테스트해보니,
      기본 내장 폰트(Helvetica 등)는 한글을 만나면 렌더링이 아니라
      `FPDFUnicodeEncodingException`으로 즉시 실패함 - 이 앱의 실제 데이터
      (학습챗 메시지, 퀴즈 문제, 면접 복기 등)는 전부 한글이라 PDF export가
      사실상 동작 불가능한 상태가 됨. 해결하려면 한글이 포함된 Unicode
      폰트 파일(보통 수 MB, 예: Noto Sans KR)을 저장소/Docker 이미지에
      직접 번들해야 하는데(python:3.11-slim 베이스 이미지엔 폰트가 전혀
      없음 - 시스템 폰트에 기대는 방식은 안 통함), 이건 "가벼운 라이브러리
      하나 추가"보다 훨씬 큰 작업(폰트 라이선스 확인, 자산 관리, 이미지
      용량 증가)이라 이번엔 들이지 않기로 함. weasyprint는 애초에 시스템
      네이티브 라이브러리(Pango/cairo 등)가 필요해 더 무거움. 데이터
      이동성(GDPR 등) 요구는 이미 JSON export로 충족되고, PDF는 "보기 좋게
      출력"용 부가 기능이라 우선순위가 낮다고 판단. 폰트 자산을 들여올
      의지가 생기면 재검토할 것.
- [x] 29. 면접연습/면접복기에도 WebSocket 스트리밍 확장 검토 — 검토 결과
      **면접복기 생성에만 부분 적용**.
      - 면접복기(`InterviewReviewService._generate_feedback`)는 `chat()`
        (자유 텍스트)를 쓰고, 복기 내용 전체를 분석하는 이 앱에서 가장 긴
        단일 생성이라 스트리밍 가치가 명확함 → `WS /interview/reviews/stream`
        추가 (학습챗과 같은 패턴: 기존 REST 유지 + 별도 경로, `chat_stream()`
        재사용, `check_rate_limit()`으로 레이트리밋 적용). PATCH(수정 시
        재생성)는 상대적으로 드문 케이스라 이번 범위에서 뺌.
      - 면접연습은 **적용 안 함** - 가장 빈번한 상호작용인 `submit_answer()`의
        턴별 응답이 `generate_json()`(구조화 출력, feedback+next_question을
        하나의 JSON으로 강제)을 쓰는데, Ollama의 제약된 JSON 생성은 토큰
        단위로 스트리밍해도 완전한 객체가 될 때까지 클라이언트가 보여줄 수
        있는 의미 있는 부분 텍스트가 안 나옴(마지막 질문이 아닌 턴은 구조상
        스트리밍 불가). 마지막 턴 피드백과 `complete_session()`의 종합
        피드백은 `chat()`을 써서 기술적으로는 가능하지만, 세션당 한 번만
        발생하는 일회성 동작이라 이번엔 우선순위를 낮게 봄 - 필요해지면
        후속 항목으로 분리할 것.

## 백로그 (6라운드)

- [x] 30. 세션(refresh token) 관리 API — 19번 항목(refresh token 재사용 탐지)의
      자연스러운 후속. 사용자가 자신의 활성 로그인 세션 목록을 보고, 특정
      세션 또는 전체 세션을 강제 로그아웃할 수 있도록
      `GET/DELETE /auth/sessions`, `DELETE /auth/sessions/{id}` 추가.
      `RefreshTokenRepository`에 `list_active_for_user`/
      `get_active_by_id_for_user`(소유권 확인 포함) 추가, `AuthService`에
      `list_active_sessions`/`revoke_session`/`revoke_all_sessions` 추가.
      **알려진 한계**: 이 API는 access_token으로 인증하는데,
      RefreshToken은 발급 당시의 access_token과 연결된 정보가 없어서
      "지금 요청을 보내는 이 기기가 목록의 몇 번째 세션인지"는 구분할 수
      없음 - 세션 개수 확인/특정·전체 로그아웃 용도로만 유효. 필요해지면
      RefreshToken에 device/user-agent 같은 식별 메타데이터를 추가하는
      후속 작업으로 개선 가능.

## 백로그 (7라운드)

- [x] 31. 퀴즈 재도전 이력 조회 API — 기존에 `GET /quizzes/{id}/result`는
      가장 최근 제출 1건만 상세히(문항별 정답 여부까지) 보여줬는데, 같은
      퀴즈를 여러 번 다시 풀었을 때 점수가 어떻게 변했는지(추이 그래프 등)
      확인할 방법이 없었음. `GET /quizzes/{id}/attempts`를 추가해 전체
      제출 이력(id/score/total/submitted_at)을 최신순으로 반환 -
      `QuizAttemptRepository.list_for_quiz`(신규), `QuizService.list_attempts`
      (소유권 검증 후 404 처리) 추가. 문항별 상세는 기존 `/result`가
      이미 담당하므로 이 응답은 점수 요약만 가볍게 준다.

## 백로그 (8라운드)

- [x] 32. 면접 연습 세션 목록에 페이지네이션 적용 — `GET
      /interview/practice-sessions`가 FRONTEND_INTEGRATION.md에 "페이지네이션
      없음 - 필요해지면 3-1(학습챗)처럼 추가 예정"이라고 이미 명시돼 있던
      후속 과제였음. 학습챗(`StudySessionRepository`/`StudyService`)과 동일한
      패턴으로 `InterviewPracticeSessionRepository.list_for_user`에
      limit/offset을 추가하고 `count_for_user`를 신설, 응답 헤더
      `X-Total-Count`로 전체 개수를 실어보냄. 기존 `list_for_user(user_id)`
      (인자 없음)를 쓰던 `ExportService`는 전량이 필요하므로
      `list_all_for_user(user_id)`(신규, 페이지네이션 없음)로 옮겨 분리했다 -
      `StudySessionRepository`가 이미 쓰던 것과 같은 list_for_user/
      list_all_for_user 이원화 패턴.

## 백로그 (9라운드)

- [x] 33. 퀴즈 목록에도 페이지네이션 적용 — 32번(면접 연습 세션 페이지네이션)과
      같은 이유로, `GET /quizzes`도 학습챗/면접연습과 동일한
      limit/offset + `X-Total-Count` 패턴을 적용했다.
      `QuizRepository.list_for_user`에 limit/offset을 추가하고
      `count_for_user`를 신설. 오답노트(`get_wrong_answer_notebook`)와
      `ExportService`처럼 전량이 필요한 곳은 신설한
      `list_all_for_user(user_id)`(페이지네이션 없음)로 옮겼다 - 지금까지
      나온 3개 목록 엔드포인트(학습챗/면접연습/퀴즈)가 전부 같은
      list_for_user(paginated)/list_all_for_user(전량) 이원화 패턴을
      공유하게 됐다.

## 백로그 (10라운드)

- [x] 34. 학습챗 세션 제목 수정(rename) API — 면접복기(`PATCH
      /interview/reviews/{id}`)는 이미 제목/내용 수정을 지원하는데, 학습챗
      세션은 생성 시 정한 제목을 바꿀 방법이 없었음(삭제 후 재생성만
      가능). `PATCH /study/sessions/{id}`(`{ "title": "..." }`, 소유권
      검증, 존재하지 않거나 남의 세션이면 404)를 추가해 제목만 가볍게
      바꿀 수 있게 함. 세션의 실질 데이터(메시지 히스토리)는 제목과
      무관하므로 재생성 로직은 필요 없어 면접복기의 PATCH보다 훨씬 단순함.

## 백로그 (11라운드)

- [x] 35. 퀴즈 삭제 API — 학습챗 세션(`DELETE /study/sessions/{id}`)과
      면접복기(`DELETE /interview/reviews/{id}`)는 이미 삭제를 지원하는데
      퀴즈만 삭제 방법이 없었음(반복 생성으로 계속 쌓이기만 함). `DELETE
      /quizzes/{id}` 추가 - 문항(QuizQuestion)/제출 이력(QuizAttempt)/
      답안(QuizAnswer)은 전부 `ondelete=CASCADE`로 이미 걸려있어(24번
      항목에서 고친 SQLite FK 강제 활성화 덕에 테스트 환경에서도 동작)
      Quiz 로우만 지우면 자동으로 함께 삭제됨. source_text를 직접
      붙여넣어 만든 퀴즈는 RAG에 색인돼 있을 수 있어 `forget_content`도
      같이 호출(study_session에서 만든 퀴즈는 애초에 색인된 게 없어
      안전하게 no-op).

## 백로그 (12라운드)

- [x] 36. 면접 연습 세션 삭제 API — 학습챗/면접복기/퀴즈는 전부 삭제를
      지원하는데 면접 연습 세션만 유일하게 삭제 방법이 없었음(CRUD
      대칭성의 마지막 빈틈). `DELETE /interview/practice-sessions/{id}`
      추가. turns는 `ondelete=CASCADE`로 DB가 알아서 지우지만, RAG 색인은
      `submit_answer()`가 세션 단위가 아니라 **문답(turn)마다 개별
      source_id로** 색인해두므로(35번 퀴즈와 다른 점), 세션을 지우기 전에
      turn id 목록을 먼저 가져와서 세션 삭제 후 각 turn id로
      `forget_content`를 반복 호출해야 했다 - 세션을 먼저 지우면 CASCADE로
      turn 로우 자체가 사라져 id를 못 가져온다.

## 백로그 (13라운드)

- [x] 37. 퀴즈 제목 수정(rename) API — 학습챗 세션(34번)은 이미 제목
      수정을 지원하는데 퀴즈는 여전히 제목을 바꿀 방법이 없었음.
      `PATCH /quizzes/{id}`(`{ "title": "..." }`, 소유권 검증, 존재하지
      않거나 남의 퀴즈면 404)를 추가 - `StudySessionRepository.update_title`/
      `StudyService.rename_session`과 완전히 같은 패턴을 `QuizRepository`/
      `QuizService`에 그대로 적용했다. 퀴즈의 문항/정답은 제목과 무관하므로
      재생성 로직 없이 제목 컬럼만 갱신.

## 백로그 (14라운드)

- [x] 38. 레이트리밋(429) 에러 응답도 통일된 `{"error": {"code",
      "message"}}` 포맷으로 - 21번 항목(에러 포맷 통일) 당시
      FRONTEND_INTEGRATION.md에 "slowapi 기본 핸들러만 예외적으로
      `{"error": "문자열"}` 포맷, 아직 통일 안 됨"이라고 명시적으로
      남겨뒀던 후속 과제. `app/core/errors.py`에 `rate_limit_exceeded_handler`
      를 새로 만들어 slowapi의 `_rate_limit_exceeded_handler` 대신 등록 -
      `Retry-After`/`X-RateLimit-*` 헤더는 slowapi의
      `Limiter._inject_headers()`를 그대로 재사용해 기존 동작을 보존하면서
      바디만 다른 에러들과 같은 구조로 바꿨다. 상태코드 429의 기본 code인
      `rate_limited`는 이미 `_DEFAULT_CODES_BY_STATUS`에 있어 그대로 재사용.

## 백로그 (15라운드)

- [x] 39. 면접 연습 submit_answer/complete_session 에러 경로 테스트 보강 -
      coverage 리포트를 훑다가 `interview_practice_service.py`가 94%로
      다른 서비스보다 낮은 걸 발견. 미달 라인이 전부 `submit_answer`/
      `complete_session`의 (1) 존재하지 않는 세션 404, (2) AI 생성 실패
      502(submit_answer는 다음 질문 생성 경로/마지막 턴 종합 피드백 경로
      둘 다) 처리였음 - 코드 자체는 이미 올바르게 구현돼 있었지만
      `create_session`/퀴즈/면접복기의 동급 생성 실패 케이스는 전부
      테스트가 있는데 이 두 메서드만 빠져 있던 테스트 커버리지 공백이었다.
      테스트 5개를 추가해 `interview_practice_service.py`를 100%로
      끌어올렸다(프로덕션 코드 변경 없음, 테스트 전용 변경).

## 백로그 (16라운드)

- [x] 40. 면접복기 update/delete 에러 경로 테스트 보강 - 39번과 같은
      방식으로 coverage 리포트를 마저 훑음. `interview_review_service.py`
      가 95%로, 미달 라인은 `update_review`의 (1) 존재하지 않는 복기
      404, (2) `position`/`interview_date` 단독 수정 분기(company/content만
      테스트돼 있었음), `delete_review`의 (3) 존재하지 않는 복기 404였음.
      테스트 6개를 추가해 100%로 끌어올렸다(프로덕션 코드 변경 없음,
      테스트 전용 변경). 39/40번으로 학습챗 대비 상대적으로 낮았던
      면접 관련 두 서비스의 커버리지 공백을 마저 정리한 것.

## 백로그 (17라운드)

- [x] 41. 게스트 계정 승격(`/users/me/upgrade`) 테스트 전무 - 39/40번과
      같은 방식으로 계속 훑던 중 `user_service.py`(91%)뿐 아니라
      `POST /users/me/upgrade` 엔드포인트 자체가 테스트 스위트에서
      **단 한 번도 호출되지 않고 있던** 걸 발견(1-0-1 문서에 소개된
      "게스트 → 실계정 전환" 기능인데도). 정상 승격, 이미 실계정인
      사용자의 재승격 시도(409), 다른 사용자가 쓰는 이메일과 충돌(409)을
      테스트로 추가. 동시에 `update_profile`/`upgrade_guest` 양쪽의
      비밀번호 72바이트 초과(멀티바이트) 에지 케이스(회원가입에는 이미
      있던 테스트인데 이 두 경로엔 없었음)도 추가해
      `user_service.py`를 100%로 끌어올렸다(프로덕션 코드 변경 없음,
      테스트 전용 변경).

## 백로그 (18라운드)

- [x] 42. 학습챗 세션 삭제/메시지전송 404 + WS 스트리밍 그라운딩 테스트
      보강 - 39~41번과 같은 방식으로 계속 훑던 중 `study_service.py`
      (97%)에서 세 가지 공백을 발견: (1) `delete_session`의 존재하지
      않는 세션 404, (2) REST `send_message`의 존재하지 않는 세션 404
      (WS `stream_message` 쪽은 이미 `test_stream_message_other_users_session_returns_error_event`로
      커버돼 있었음), (3) WS 스트리밍 경로(`stream_message`)의 RAG
      그라운딩 분기 - REST `send_message`는 그라운딩 테스트가 있었는데
      WS 버전엔 대응하는 테스트가 없었다(`GroundingFakeOllamaService`에
      `chat_stream`이 아예 없었음). 테스트 3개를 추가해
      `study_service.py`를 100%로 끌어올렸다(프로덕션 코드 변경 없음,
      테스트 전용 변경).

## 백로그 (19라운드)

- [x] 43. 퀴즈 제출/결과조회 검증 실패 경로 테스트 보강 - 39~42번과
      같은 방식으로 마지막 남은 핵심 서비스인 `quiz_service.py`(97%)를
      정리. 미달 라인은 `get_wrong_answer_notebook`의 "제출 이력이 아예
      없는 퀴즈는 건너뛴다" 분기(기존 빈 오답노트 테스트는 퀴즈 자체를
      안 만들어서 이 분기를 타지 않았음), `submit_answers`의 존재하지
      않는 퀴즈 404/중복 문항 답안 400/선택지 인덱스 범위 초과 400,
      `get_latest_result`의 존재하지 않는 퀴즈 404(기존 테스트는 "퀴즈는
      있는데 제출 이력이 없는" 케이스만 다뤘음)였다. 테스트 6개를
      추가해 `quiz_service.py`를 100%로 끌어올렸다(프로덕션 코드 변경
      없음, 테스트 전용 변경) - 이로써 39~43번에 걸쳐 학습챗/퀴즈/면접
      연습/면접복기/사용자 5개 핵심 서비스 전부 100% 커버리지 달성.

## 백로그 (20라운드)

- [x] 44. RAG 서비스 빈 임베딩/빈 콘텐츠 경로 테스트 보강 - 39~43번
      시리즈를 `rag_service.py`(91%)로 이어감. 미달 라인은 `index_content`의
      (1) 공백만 있는 content는 임베딩 호출 자체를 건너뛰는 분기,
      (2) `embed()`가 예외 없이 빈 벡터(`[]`)를 반환하는(장애가 아니라
      모델 쪽 이상 응답) 경우 건너뛰는 분기, `retrieve_relevant`의
      (3) 질의 임베딩이 빈 벡터로 오는 같은 케이스였다 - 기존 테스트는
      전부 `OllamaServiceError` 예외 케이스만 다뤘지 "호출은 성공했지만
      빈 벡터"라는 별개의 실패 모드는 다루지 않고 있었다. `RagService`는
      API 계층을 거치지 않고 직접 단위테스트하는 `test_rag_service.py`가
      이미 있어 그 안에 신규 `EmptyEmbeddingOllamaService` 더블과 함께
      테스트 3개를 추가해 100%로 끌어올렸다(프로덕션 코드 변경 없음,
      테스트 전용 변경).

## 백로그 (21라운드)

- [x] 45. RAG 백필 스케줄러 잡(`run_scheduled_rag_backfill`) 정상 동작/
      예외 경로 테스트 보강 - 39~44번 시리즈의 마지막으로
      `rag_backfill_service.py`(88%)를 정리. 기존엔 "DB 엔진 미초기화"
      경고 분기만 테스트돼 있었고, 정작 정상적으로 색인하고 건수를
      로그로 남기는 happy path와 예상 못한 예외(`except Exception`)를
      잡아 `logger.exception`으로 남기는 분기는 테스트가 없었다 - 이
      함수는 앱 전역 DB 엔진(`app.db.session._session_factory`)과
      직접 생성하는 `OllamaService`에 의존해 기존 테스트 더블 주입
      방식으로는 검증할 수 없었으므로, 테스트 안에서 임시로 별도
      SQLite 엔진을 그 전역 상태에 채웠다가 `try/finally`로 반드시
      되돌리는 헬퍼(`_with_initialized_engine`)를 새로 만들고
      `OllamaService.embed`는 monkeypatch로 스텁 처리했다. 테스트 2개를
      추가해 `rag_backfill_service.py`를 100%로 끌어올렸다(프로덕션
      코드 변경 없음, 테스트 전용 변경) - 이로써 실제 네트워크 I/O를
      감싸기만 하는 `ollama_service.py`(75%, 각 메서드가 거의 그대로
      httpx 호출이라 별도 커버리지 목표로 삼지 않기로 함)를 제외한
      전체 서비스 계층이 100% 커버리지에 도달했다.

## 백로그 (22라운드)

- [x] 46. 학습챗 WS 스트리밍 메시지 길이 제한 테스트 추가 - 서비스
      계층이 전부 100%가 되어 라우트 계층으로 넘어가 훑던 중,
      `study.py`의 WS 스트리밍 라우트(`/study/sessions/{id}/stream`)가
      REST(`POST .../messages`)와 별개로 `max_prompt_length`를 직접
      체크하는 로직을 갖고 있는데(WS 페이로드는 raw dict라 pydantic
      스키마의 자동 길이 검증을 안 타서 라우트에서 수동으로 다시
      검사함) 이 분기가 테스트되지 않고 있던 걸 발견. REST 쪽엔
      `test_chat.py` 등에 `MAX_PROMPT_LENGTH` 초과 테스트가 있는데
      WS 쪽엔 빈 내용(공백) 테스트만 있고 길이초과 테스트가 없었다.
      테스트 1개를 추가했다(프로덕션 코드 변경 없음, 테스트 전용
      변경).

## 백로그 (23라운드)

- [x] 47. WS 인증(`get_current_user_ws`) 실패 경로 테스트 보강 - 46번에
      이어 라우트/핵심 인프라 계층을 계속 훑다가 `core/dependencies.py`
      (93%)에서 두 분기를 발견: (1) 형식이 잘못된(서명 위조/만료 등이
      아니라 애초에 JWT가 아닌) 토큰, (2) 형식은 유효하지만 가리키는
      사용자가 더 이상 존재하지 않는 토큰(탈퇴한 계정의 access token으로
      재접속 시도) - 두 경우 모두 WS를 정책 위반(1008)으로 끊어야
      하는데, 기존엔 "토큰 자체가 없는" 케이스만 학습챗/면접복기 WS
      양쪽에 테스트돼 있었다. `test_study.py`에 두 테스트를 추가해
      `core/dependencies.py`를 100%로 끌어올렸다(프로덕션 코드 변경
      없음, 테스트 전용 변경).

## 백로그 (24라운드)

- [x] 48. `app/core/tokens.py` 단위 테스트 파일 신설 - 47번에 이어 핵심
      인프라 계층을 계속 훑다가, JWT 발급/검증을 담당하는 이 모듈이
      지금까지 전용 테스트 파일 없이 auth 플로우 통합 테스트를 통해서만
      간접적으로만 검증되고 있었다는 걸 발견. 특히
      `decode_access_token`의 "type 클레임이 'access'가 아니면 거부"
      분기는 리프레시 토큰이 애초에 JWT가 아니라 불투명한 랜덤
      문자열이라 API 경로로는 절대 트리거될 수 없는, 미래의
      타입 혼동(type confusion) 공격에 대비한 방어선인데 단 한 번도
      실행된 적이 없었다. `tests/test_tokens.py`를 새로 만들어 발급/
      복호화 왕복, 잘못된 type 클레임 거부, 만료된 토큰 거부, 잘못된
      시크릿 거부, refresh token 생성/해시/만료시각 계산까지 직접
      단위테스트로 커버해 `core/tokens.py`를 100%로 끌어올렸다
      (프로덕션 코드 변경 없음, 테스트 전용 변경).

## 백로그 (25라운드)

- [x] 49. 요청 스키마 길이/개수 제한 검증 테스트 보강 - 48번에 이어
      스키마 계층을 훑다가, `create_review`(면접복기)는 content 길이
      제한 테스트가 있는데 그 외 비슷한 검증들은 대부분 테스트가
      없었던 걸 발견: 퀴즈 생성의 `source_text` 길이 초과/
      `question_count` 상한 초과(`schemas/quiz.py`), 면접 연습
      답변(`answer`)의 `max_prompt_length` 초과(`schemas/interview_practice.py`),
      면접복기 **수정**(PATCH) 요청의 content 길이 초과(생성 쪽과 별개의
      field_validator라 생성 테스트로는 안 잡힘, `schemas/interview_review.py`),
      학습챗 REST 메시지 전송의 `max_prompt_length` 초과(WS 쪽은
      46번에서 이미 보강함, `schemas/study.py`) - 전부 422를 돌려줘야
      하는데 실제로 그런지 검증된 적이 없었다. 테스트 5개를 추가해
      네 스키마 파일 모두(사실상) 100%에 근접하게 끌어올렸다(프로덕션
      코드 변경 없음, 테스트 전용 변경).

## 백로그 (26라운드)

- [x] 50. Redis 헬스체크 성공 경로 테스트 추가 - 49번에 이어 계속
      훑다가 `core/health.py`의 `check_redis_health`가 지금까지
      **실패 경로만** 직접 단위테스트돼 있었다는 걸 발견(존재하지 않는
      포트로 연결 시도). 라우트 레벨 테스트(`test_health.py`)들은
      전부 이 함수 자체를 monkeypatch로 통째로 대체해버려서 실제
      구현(`client.ping()` 성공 시 `return True`)은 한 번도 실행된 적이
      없었다. 이 샌드박스엔 실제 Redis 서버가 없어(다른 서비스
      테스트들처럼 Fake 클라이언트로 검증하는 게 기존 컨벤션과도
      맞음) `redis.asyncio.from_url`을 monkeypatch로 대체해 `ping()`이
      성공하는 가짜 클라이언트를 주입하는 방식으로 테스트 1개를
      추가해 `core/health.py`를 100%로 끌어올렸다(프로덕션 코드 변경
      없음, 테스트 전용 변경).

## 백로그 (27라운드)

- [x] 51. `app/db/session.py` 정상 초기화 경로 테스트 보강 - 50번에
      이어 계속 훑다가 이 모듈이 66%로 가장 낮았던 걸 발견. `init_engine`/
      `close_engine`/`get_db`/`keep_supabase_alive`/
      `cleanup_expired_refresh_tokens`/`check_db_health` 전부 "엔진이
      아직 초기화 안 됐을 때"의 방어 분기만 테스트돼 있었고, 실제로
      엔진을 초기화한 뒤 정상 동작하는 happy path와 쿼리 실패 시의
      예외 처리 분기는 전부 미검증이었다(45번에서 다룬
      `run_scheduled_rag_backfill`과 같은 성격의 공백). 45번의
      전역 엔진 임시 교체 패턴을 재사용하되, `init_engine`이
      `pool_size`/`max_overflow`를 그대로 `create_async_engine`에
      넘기는 탓에 SQLite `:memory:` URL(기본 poolclass가 이 kwarg를
      안 받는 StaticPool)은 못 쓴다는 걸 확인하고, 대신 임시 파일
      기반 SQLite URL(운영의 Postgres처럼 AsyncAdaptedQueuePool을 씀)로
      우회했다. 테스트 8개를 추가해(정상 초기화/해제 왕복,
      `enable_sqlite_foreign_keys`의 non-sqlite no-op 분기 포함)
      `db/session.py`를 100%로 끌어올렸다(프로덕션 코드 변경 없음,
      테스트 전용 변경) - 이로써 `ollama_service.py`(실제 네트워크
      I/O 래퍼, 별도 목표로 삼지 않기로 함)를 제외한 앱 전체가 사실상
      100% 커버리지에 도달했다.

## 백로그 (28라운드)

- [x] 52. FRONTEND_INTEGRATION.md의 오래된 에러 응답 예시 수정 -
      코드 커버리지가 사실상 한계에 도달해 이번엔 문서 정확성을
      다시 훑음. 21번 항목에서 모든 에러 응답을 `{"error": {"code",
      "message"}}`로 통일했는데(38번에서 레이트리밋까지 마저 통일),
      "1-2. 로그인"과 "1-3. 인증이 필요한 요청" 섹션에는 통일 이전의
      `{"detail": "..."}` 형태 예시가 그대로 남아 있었다 - "2. 공통
      에러 규칙" 섹션의 통일 안내와 실제로 모순되는 상태였다. 실제
      코드(`_INVALID_CREDENTIALS`/`_CREDENTIALS_ERROR`)를 확인해 정확한
      `code`/`message` 값으로 예시를 갱신하고, 지금까지 상태 코드만
      확인하던 관련 테스트 2개에 `error.code` 값 검증도 추가해 문서와
      실제 동작이 일치함을 보장했다(WebSocket 이벤트의
      `{"type": "error", "detail": "..."}`는 REST 에러 포맷과 무관한
      별개 규약이라 그대로 둠).

## 백로그 (29라운드)

- [x] 53. 전역 예외 처리기(catch-all)를 실제로 검증하지 못하던 테스트
      수정 - 문서/코드 정합성을 계속 점검하다가 `app/main.py`의
      `@app.exception_handler(Exception)`(라우트가 못 잡은 완전히 예상
      못한 예외를 위한 최후의 안전망)가 89-90번 줄이 미커버 상태인 걸
      발견했는데, 정작 `test_unhandled_exception_returns_internal_error_code`
      라는 이름의 테스트가 이미 있었다. 확인해보니 이 테스트는
      `/api/v1/chat` 라우트가 **명시적으로 잡아** `HTTPException(500,
      문자열 detail)`로 바꾸는 `OllamaServiceError`만 일으키고
      있어서, 실제로는 전역 catch-all이 아니라 그냥 상태코드 기반
      기본 code 경로(우연히 같은 `internal_error` 값이 나옴)를 검증하고
      있었다 - 이름과 실제로 하는 일이 다른, 진짜 버그가 있어도 못
      잡아내는 테스트였다. 기존 테스트는 이름을 정확하게 바꾸고,
      라우트가 절대 못 잡는 `RuntimeError`를 직접 일으키는 새 테스트를
      추가해 진짜 전역 핸들러 경로를 검증하도록 했다 - `app/main.py`를
      100%로 끌어올렸다(프로덕션 코드 변경 없음, 테스트 정확성 수정
      + 신규 테스트 1개).

## 백로그 (30라운드)

- [x] 54. 접근 로그의 user_id 추출(`_extract_user_id`) - 잘못된 인증
      스킴 분기 테스트 추가 - 53번에 이어 계속 훑다가
      `core/middleware.py`(98%)에서 마지막 남은 분기를 발견: 로깅용
      부가 정보로 access token의 sub를 뽑는 `_extract_user_id`가
      `Authorization` 헤더는 있지만 스킴이 `Bearer`가 아닌 경우(예:
      `Basic ...`)를 안전하게 `None`으로 처리하는 분기 - 헤더 없음/
      정상 Bearer 토큰 케이스는 이미 테스트돼 있었는데 이 중간
      케이스만 빠져 있었다. 이 함수는 요청을 막지 않는 순수 로깅
      부가기능이라 실패해도 서비스에 영향은 없지만, 조용히 실패하는
      코드일수록 검증이 없으면 회귀를 못 알아챈다는 점에서 의미가
      있었다. 테스트 1개를 추가해 `core/middleware.py`를 100%로
      끌어올렸다(프로덕션 코드 변경 없음, 테스트 전용 변경) - 이로써
      `ollama_service.py`(네트워크 I/O 래퍼)와 CASCADE로 사실상 도달
      불가능한 `auth_service.py`의 방어적 분기 한 줄을 제외한 앱
      전체가 100% 커버리지에 도달했다.

## 백로그 (31라운드)

- [x] 55. JWT_SECRET_KEY 최소 길이 검증 추가 (보안 강화) - 코드
      커버리지가 사실상 한계에 도달해 이번엔 보안 관점으로 다시
      훑음. `app/core/config.py`의 `jwt_secret_key`는 필수값으로만
      선언돼 있고 길이 제약이 전혀 없어서, 운영자가 실수로
      `"secret"`이나 `"changeme"`처럼 극히 짧고 추측하기 쉬운 값을
      넣어도 앱이 조용히 정상 기동해버리는 문제가 있었다(`.env.example`
      주석에 `openssl rand -hex 32` 권장은 이미 있었지만 강제하지는
      않았음 - PyJWT의 `InsecureKeyLengthWarning`도 경고만 띄우고
      막지는 않는다). `Settings`에 `field_validator`를 추가해 32자
      미만이면 앱 기동 자체(Settings 생성 시점의 pydantic
      ValidationError)를 막도록 했다 - 운영 환경에서 취약한 시크릿이
      배포되는 걸 코드 리뷰가 아니라 시스템 차원에서 원천 차단한다.
      `.env.example` 주석도 "경고만 뜸"에서 "기동 자체가 거부됨"으로
      갱신. `tests/test_config.py`를 신설해 정상 길이 통과/짧은 값
      거부/빈 문자열 거부를 검증했다.

## 백로그 (32라운드)

- [x] 56. `/auth/refresh`, `/auth/logout`에 레이트리밋 누락 - 55번에
      이어 보안 관점으로 계속 훑다가, `auth.py`의 signup/login/guest/
      revoke_session/revoke_all_sessions는 전부 `auth_rate_limit`
      데코레이터가 붙어있는데 `refresh`/`logout`만 빠져있는 걸 발견.
      refresh_token 자체는 256비트 엔트로피라 무차별대입은 비현실적이지만,
      제한이 없으면 (1) FRONTEND_INTEGRATION.md가 권장하는 "401→refresh→
      재시도" 패턴이 클라이언트 버그로 무한루프에 빠졌을 때 브레이크가
      없고, (2) refresh는 재사용 탐지 시 `revoke_all_for_user`
      (DB write)까지 도는 로직이라 특정 계정을 겨냥한 반복 호출로
      의도치 않은 부하를 줄 수 있었다. 이 파일의 다른 라우트들과
      같은 패턴(`@limiter.limit(lambda: get_settings().auth_rate_limit)`)을
      두 라우트에 그대로 적용하고, 실제로 429가 걸리는지 테스트 2개를
      추가했다. `docs/FRONTEND_INTEGRATION.md`의 refresh 섹션과 공통
      레이트리밋 요약에도 반영.

## 백로그 (33라운드)

- [x] 57. HSTS(Strict-Transport-Security) 헤더 추가 - 55/56번에 이어
      보안 관점으로 계속 훑다가 `SecurityHeadersMiddleware`가
      `X-Content-Type-Options`/`X-Frame-Options`/`Referrer-Policy`는
      붙이면서 `Strict-Transport-Security`는 빠뜨린 걸 발견. 이 앱은
      Caddy 리버스 프록시 뒤에서 HTTPS로만 서빙되는 걸 전제로 하는데
      (`FRONTEND_INTEGRATION.md` 0장 참고) HSTS가 없으면 프로토콜
      다운그레이드(HTTPS→HTTP 유도) 공격에 대한 표준 방어선이 빠진
      상태였다. 이 헤더는 스펙상 브라우저가 평문 HTTP 응답에서는
      무시하므로 로컬 http 개발 환경에는 영향 없이 항상 붙여도
      안전하다 - 환경별 분기 없이 `max-age=63072000; includeSubDomains`
      (2년, 서브도메인 포함)로 추가하고 테스트를 갱신했다.

## 백로그 (34라운드)

- [x] 58. 로그인 타이밍 공격(계정 존재 여부 유출) 방지 - 55~57번에 이어
      보안 관점으로 계속 훑다가 `AuthService.login()`에서 실제
      취약점을 발견: `if user is None or ... or not verify_password(...)`가
      `or`로 단축 평가되기 때문에, 존재하지 않는 이메일로 로그인
      시도하면 `verify_password`(bcrypt 비교, 수십~수백ms)를 아예
      건너뛰고 즉시 401을 반환하지만 존재하는 이메일에 틀린 비밀번호를
      넣으면 bcrypt 비교까지 다 수행한 뒤 401을 반환한다 - 이 응답
      시간 차이를 측정하면 이메일 목록을 무차별로 넣어보며 어떤
      이메일이 가입돼 있는지 추측할 수 있는 고전적인 타이밍 기반
      계정 존재 여부 유출이었다. `core/password.py`의
      `verify_password`가 `hashed_password=None`일 때 아무의
      비밀번호도 아닌 캐싱된 더미 해시와 비교하도록 바꾸고,
      `AuthService.login()`은 사용자 존재 여부와 무관하게
      `verify_password`를 매번 호출하도록 재구성해 응답 시간을
      균일하게 만들었다. `tests/test_password.py`를 신설하고
      `test_auth.py`에 존재하지 않는 이메일 로그인 테스트를 추가했다.

## 백로그 (35라운드)

- [x] 59. uvicorn이 Caddy의 X-Forwarded-For를 신뢰하지 않던 문제
      (IP 기준 레이트리밋 사실상 무력화) - 55~58번에 이어 보안/인프라
      관점으로 계속 훑다가 심각한 인프라 버그를 발견. `docker-compose.yml`
      구성상 `haruhan-backend` 컨테이너는 호스트에 포트를 노출하지
      않고 Caddy 리버스 프록시를 거쳐서만 트래픽을 받는데, `Dockerfile`의
      uvicorn 실행 커맨드에 `--proxy-headers`가 없어서 Caddy가 보내는
      `X-Forwarded-For`를 아예 무시하고 있었다. 그 결과 slowapi의
      `get_remote_address()`(레이트리밋 키), WS 라우트의
      `websocket.client.host`(WS 레이트리밋 키), `AccessLogMiddleware`의
      `scope["client"]`(접근 로그) 전부가 실제 사용자 IP가 아니라
      **항상 Caddy 컨테이너의 내부 IP**를 봤다는 뜻 - 즉 `auth_rate_limit`/
      `chat_rate_limit`이 사용자별이 아니라 전체 트래픽이 하나의 버킷을
      공유하는 것과 같아져서, 한 사용자(또는 악의적 요청)가 다른 모든
      사용자를 429로 몰아넣을 수 있는 사실상 레이트리밋 무력화 +
      DoS 벡터였다. `Dockerfile`의 uvicorn CMD에 `--proxy-headers
      --forwarded-allow-ips=*`를 추가했다 - 백엔드 포트 자체가
      호스트/외부에 노출되지 않아 Caddy를 거치지 않고 직접 접속해
      헤더를 위조할 방법이 없으므로 `*`를 써도 안전하다. 이 fix는
      ASGI 트랜스포트 계층(uvicorn)에서 한 번에 적용돼 레이트리밋/
      WS/로깅 세 곳 모두를 동시에 고친다. `tests/test_dockerfile.py`를
      신설해 이 플래그가 CMD에서 조용히 빠지는 회귀를 막는 테스트를
      추가했다(애플리케이션 코드 밖의 인프라 설정이라 pytest로 직접
      기동 검증은 못 하지만, 텍스트 존재 여부는 검증).

## 백로그 (36라운드)

- [x] 60. `MaxBodySizeMiddleware`의 413 응답이 통일된 에러 포맷을 안 쓰던
      버그 수정 - 55~59번에 이어 보안/인프라 관점으로 계속 훑다가
      실제 코드 버그를 발견. 21번 항목(에러 포맷 통일)과 38번 항목
      (레이트리밋 429까지 통일)을 거쳤는데도, `MaxBodySizeMiddleware`
      (요청 본문이 `MAX_BODY_SIZE_BYTES`를 넘으면 413으로 막는
      ASGI 미들웨어)만 여전히 예전 `{"detail": "..."}` 포맷으로 직접
      `JSONResponse`를 만들고 있었다 - 이 미들웨어는 FastAPI
      라우팅/예외 핸들러 계층 바깥(ASGI 레벨)에서 응답을 완성해버려서
      `app.core.errors`의 `http_exception_handler`를 거치지 않기
      때문에, 21/38번 리팩터링 때 놓쳤던 것. `_DEFAULT_CODES_BY_STATUS`에
      이미 `413: "payload_too_large"`가 정의돼 있었는데도 정작 이
      경로에서는 안 쓰이고 있었다. `build_error_body()`를 직접
      재사용해 나머지 모든 에러와 같은 `{"error": {"code",
      "message"}}` 포맷이 되도록 고치고, 기존 테스트(상태코드만
      확인하던)에 `error.code` 검증을 추가했다.

## 백로그 (37라운드)

- [x] 61. CORS `expose_headers` 누락으로 프론트가 페이지네이션/레이트리밋
      헤더를 못 읽던 버그 수정 - 60번에 이어 계속 훑다가 중대한 버그를
      발견. `main.py`의 `CORSMiddleware` 설정에 `expose_headers`가
      아예 없어서 기본값(빈 목록)이 적용되고 있었다 - 브라우저는
      cross-origin 응답에서 "CORS-safelisted" 헤더 극소수만 JS에 기본
      노출하고, 그 외는 서버가 `Access-Control-Expose-Headers`로 명시
      허용해야 `fetch()`의 `response.headers.get(...)`으로 읽을 수
      있다. 그런데 `FRONTEND_INTEGRATION.md`는 여러 라운드(18/32/33번
      등 페이지네이션, 2장 레이트리밋 안내)에 걸쳐 프론트가
      `X-Total-Count`/`X-RateLimit-Limit`/`X-RateLimit-Remaining`/
      `X-RateLimit-Reset`/`Retry-After`를 **직접 읽으라고** 안내해왔다 -
      이 프로젝트는 Vercel에 배포된 프론트가 다른 도메인의 이 API를
      호출하는(`.env.example`의 `CORS_ORIGINS` 예시가 바로 그 형태)
      cross-origin 구조라서, 실제 운영 환경에서는 이 헤더들이 응답에
      실려 와도 프론트 JS에서는 전부 `null`로 보였을 것이다. 직접
      `Origin` 헤더를 넣어 재현 확인 후(`access-control-expose-headers`
      가 응답에 아예 없음) `CORSMiddleware`에 `expose_headers`로 다섯
      헤더를 명시했다. `tests/test_cors.py`를 신설해 노출 목록,
      허용된/안 허용된 origin 분기까지 검증했다(이전엔 CORS 전용
      테스트가 아예 없었다).

## 백로그 (38라운드)

- [x] 62. CI에 `alembic check` 단계 추가 - 마이그레이션/모델 드리프트가
      머지될 때까지 아무도 못 잡던 구멍을 발견. `tests/conftest.py`의
      `db_session_factory` 픽스처는 `Base.metadata.create_all()`로
      SQLite에 스키마를 직접 만들어서 쓰기 때문에, alembic 마이그레이션
      체인을 완전히 건너뛴다 - 즉 모델을 고치고 그에 맞는 마이그레이션
      파일을 깜빡해도 `pytest`는 100% 초록불이고, `mypy`/`pip-audit`/
      `gitleaks`로 구성된 기존 CI(`.github/workflows/ci.yml`)도 이걸
      전혀 검사하지 않았다. 실제로 스키마가 어긋나는지는 `alembic
      check`만 확인할 수 있는데, 이건 진짜 DB 연결이 필요하고
      (`migrations/env.py`가 `DATABASE_URL`로 엔진을 만듦) SQLite가
      아니라 운영과 같은 Postgres 방언이어야 신뢰할 수 있다. CI에
      `postgres:16` 서비스 컨테이너를 띄우는 `migrations` job을 새로
      추가해 `alembic upgrade head` 후 `alembic check`를 돌리도록
      했다 - `requirements-dev.txt`가 `requirements.txt`를 통해
      `alembic`/`asyncpg`를 이미 포함하고 있어 별도 설치는 필요
      없었다. `Settings.jwt_secret_key`가 55번부터 32자 이상을
      요구하므로, `get_settings()`가 호출되는 순간(alembic이 서버는
      안 띄워도 `Settings()`는 생성함) 검증을 통과하도록 CI 전용
      더미 `JWT_SECRET_KEY`를 env로 넣었다. 로컬 Postgres 클러스터에
      대고 CI와 동일한 두 명령을 직접 재현해 통과를 확인했다.

## 백로그 (39라운드)

- [x] 63. 이메일 대소문자 미정규화로 중복 계정이 생기던 버그 수정 - 62번에
      이어 계속 훑다가 발견. `User.email`은 `unique=True` 제약이
      걸려 있지만 Postgres/SQLite 둘 다 기본은 대소문자를 구분하는
      비교라서, `SignupRequest`/`LoginRequest`/`GuestUpgradeRequest`/
      `UserUpdateRequest`가 입력값을 그대로(`EmailStr` 형식 검증만
      거쳐) DB에 넣거나 비교하고 있었다 - `User@Example.com`으로
      가입한 뒤 `user@example.com`으로 로그인하면 "계정이 없다"고
      나오거나, 최악의 경우 대소문자만 다른 이메일로 같은 메일함
      소유자가 별개 계정을 하나 더 만들 수 있었다(unique 제약이
      막지 못함). `app/schemas/validators.py`를 신설해
      `NormalizedEmail`(strip 후 소문자 변환하는 `AfterValidator`를
      붙인 `EmailStr` 타입 별칭)을 만들고, 이메일을 입력받는 네
      스키마 전부에 적용했다. 이렇게 하면 앞으로 저장되는 이메일은
      전부 소문자라서 기존 `unique=True` 컬럼 제약만으로도 대소문자
      무관 유일성이 그대로 보장되므로, 마이그레이션이나 DB 스키마
      변경은 필요 없었다(`alembic check`로 드리프트 없음 재확인).
      이미 대소문자가 섞인 채로 저장된 과거 데이터를 소급 정리하는
      건 실제 운영 데이터에서 충돌 사례를 수동으로 판단해야 할 수
      있어 이번 라운드 범위 밖으로 남겨뒀다. `tests/
      test_schemas_validators.py`를 신설해 네 스키마의 정규화
      동작을 검증하고, `test_auth.py`에 대소문자만 다른 재가입이
      `409`가 되는지·대소문자 다른 이메일로 로그인이 되는지 End-to-End
      테스트를 추가했다. `FRONTEND_INTEGRATION.md`의 회원가입 절에
      이 동작을 안내하는 문장을 추가했다.

## 백로그 (40라운드)

- [x] 64. 422 검증 오류 응답이 비밀번호 등 민감한 값을 평문으로 노출하던
      버그 수정 - 63번에 이어 계속 훑다가 발견. Pydantic의
      `RequestValidationError.errors()`는 각 오류 항목에 검증에
      실패한 필드의 원본 입력값을 `"input"` 키로 그대로 담는다.
      `app/core/errors.py`의 `validation_exception_handler`가 이
      `errors()`를 가공 없이 그대로 `details`에 실어 보내고 있었기
      때문에, 예를 들어 회원가입 시 8자 미만 비밀번호를 보내면 422
      응답 바디에 그 평문 비밀번호가 `input` 필드로 그대로 실려
      나갔다 - 프론트 개발 도구(devtools) 네트워크 탭 히스토리나
      API 요청/응답을 수집하는 모니터링·로깅 도구(Sentry 등)에
      비밀번호가 평문으로 남을 수 있는 실질적인 노출 경로였다.
      직접 재현해 확인(`SignupRequest(password="short")`의
      `.errors()`에 `"input": "short"`가 그대로 담김) 후, 핸들러에서
      각 오류 dict의 `input` 키를 제거하고 나머지(`loc`/`type`/`msg`/
      `ctx`)는 그대로 남기도록 고쳤다 - `FRONTEND_INTEGRATION.md`가
      이미 `details`의 필드로 `loc`/`msg`/`type`만 안내하고 있어서
      문서 변경은 필요 없었다. `tests/test_error_format.py`에
      응답 어디에도 `"input"` 키가 없고 `loc`은 여전히 정확한지
      검증하는 테스트를 추가했다.

## 백로그 (41라운드)

- [x] 65. DB 엔진에 `pool_pre_ping` 누락 - 끊긴 커넥션으로 첫 요청이
      500으로 실패하던 문제 예방 - 64번에 이어 계속 훑다가 발견.
      `app/db/session.py`의 `init_engine()`이 `create_async_engine`에
      `pool_size`/`max_overflow`만 넘기고 `pool_pre_ping`은 켜지
      않고 있었다. 이 프로젝트는 `keep_supabase_alive()`로 Supabase
      DB의 7일 자동 정지(inactivity pause)를 막고 있지만, 이건
      APScheduler cron으로 **하루에 한 번**만 도는 별개의 방어선이라,
      Supabase의 커넥션 풀러(pgbouncer 등)가 그보다 훨씬 짧은 주기로
      유휴 커넥션을 서버 쪽에서 조용히 끊는 것까지는 막지 못한다 -
      `pool_pre_ping` 없이는 SQLAlchemy가 이미 끊긴 커넥션을 풀에서
      그대로 꺼내 쓰다가 첫 쿼리에서 예외가 나고, 그게 어디서도
      잡히지 않아 사용자 요청이 그대로 500으로 실패한다. 매
      체크아웃 전에 가벼운 `SELECT 1`로 살아있는지 확인하고 죽어
      있으면 조용히 새 커넥션으로 교체하도록 `pool_pre_ping=True`를
      추가했다. 모델/스키마 변경이 아니라 엔진 생성 옵션이라
      마이그레이션은 필요 없었다(`alembic check`로 드리프트 없음
      재확인). `tests/test_db_session.py`에 `_engine.pool._pre_ping`
      이 `True`인지 확인하는 테스트를 추가했다 - 실제 커넥션 드롭
      재현은 mock 없이는 어려워 설정값 자체를 검증하는 선에서
      그쳤다.

## 백로그 (42라운드)

- [x] 66. RAG 백필 cron이 매일 전체 이력을 훑던 비효율 수정 - 65번에
      이어 계속 훑다가 발견. `study_service`/`interview_review_service`는
      학습챗 메시지/면접 복기를 만드는 시점에 이미 동기로
      `rag_service.index_content()`를 호출해 색인한다 - 즉
      `rag_backfill_service.backfill_unindexed_content()`(매일
      새벽 5시 APScheduler cron)가 정상 상태에서 실제로 찾아내는
      건 임베딩 API 일시 실패 같은 극소수 예외 케이스뿐이다. 그런데
      기존 구현은 "안 된 것만 찾는다"면서 정작 `study_messages`/
      `interview_reviews` 테이블 **전체**를 파이썬으로 읽어오고,
      `knowledge_chunks`의 색인된 source_id 전체 집합도 따로
      읽어와서 파이썬에서 대조하고 있었다 - 서비스가 오래될수록
      거의 모든 행이 이미 색인된 상태가 되므로, 이 cron이 매일
      서비스 전체 이력 규모로 계속 커지는 조회/메모리 사용을
      영원히 반복하는 셈이었다. `study_message`/`interview_review`
      각각에 `knowledge_chunks`를 `(source_type, source_id)` 조건으로
      LEFT JOIN해서 `WHERE 색인.id IS NULL`로 아직 색인 안 된 행만
      SQL 단에서 걸러내도록 바꿨다 - `index_content()`가 색인 전에
      항상 기존 걸 먼저 지우므로(source당 최대 1개) 조인으로 행이
      중복될 걱정은 없다. 기존 `KnowledgeChunkRepository.
      get_indexed_source_ids()`는 다른 테스트에서 여전히 널리 쓰여서
      그대로 남겨뒀다. 새 인덱스/마이그레이션 없이도(`source_id`에
      이미 index=True가 있음) 충분해 스키마 변경은 하지 않았다
      (`alembic check`로 드리프트 없음 재확인). 기존 백필 테스트가
      그대로 통과하는 것으로 동작 동등성을 확인했고, 미리 색인해둔
      메시지가 여러 개 섞여 있어도 아직 색인 안 된 것만 정확히
      골라내는지 검증하는 테스트를 추가했다.

## 백로그 (43라운드)

- [x] 67. 면접 연습 `/complete`에 레이트리밋 누락 - LLM 호출 경로인데
      비용 제한이 안 걸려 있던 문제 수정 - 66번에 이어 계속 훑다가
      발견. `interview_practice.py`의 `create_session`/
      `submit_answer`는 둘 다 `@limiter.limit(lambda: get_settings().
      chat_rate_limit)`이 걸려 있는데, 같은 라우터의
      `POST /{session_id}/complete`만 그 데코레이터와
      `request`/`response` 파라미터가 빠져 있었다. 서비스 코드를
      보면 `complete_session()`도 종합 피드백을 생성하려고 다른
      두 경로와 똑같이 `self._ollama.chat(...)`을 호출하므로,
      LLM 호출 비용을 막으려고 두는 `chat_rate_limit`이 정확히
      적용됐어야 할 세 번째 경로였다 - 세션이 이미 `completed`
      상태여도 slowapi 데코레이터는 라우트 핸들러 본문(404/409
      체크)보다 먼저 카운트를 소비하므로, 존재하지 않는/이미 끝난
      세션 id로 반복 호출하는 것만으로도 무제한으로 호출을
      시도할 수 있었다(각 시도 자체는 LLM까지 안 가고 실패하지만,
      실제 진행 중인 세션에 대해서는 그대로 무제한 LLM 호출로
      이어진다). 다른 두 경로와 동일하게 데코레이터 + `request`/
      `response` 파라미터를 추가했다. 모델/스키마 변경이 아니라
      마이그레이션은 필요 없었다(`alembic check`로 드리프트 없음
      재확인). `tests/test_interview_practice.py`에 존재하지 않는
      세션 id로 반복 호출해도 레이트리밋이 걸리는지 확인하는
      테스트를 추가했고, `FRONTEND_INTEGRATION.md`의 면접 연습
      절에 `/complete`도 `chat_rate_limit` 대상이라는 문장을
      추가했다.

## 백로그 (44라운드)

- [x] 68. mypy가 타입 힌트 없는 함수를 조용히 통과시키던 구멍 수정 -
      67번에 이어 계속 훑다가 발견. `mypy.ini`가 `ignore_missing_imports`
      말고는 아무 엄격 옵션도 안 켜져 있었는데, mypy 기본값은 시그니처가
      아예 없는 함수는 본문 검사 자체를 건너뛴다 - 즉 새 함수를 타입
      힌트 없이 추가해도 CI의 `mypy app tests` 단계가 절대 못 잡아내는
      사각지대였다. 직접 `app/core/cache.py`에 힌트 없는 함수를 추가해
      기존 설정으로는 통과함을 재현 확인했다. `[mypy-app.*]
      disallow_untyped_defs = True`를 추가해 프로덕션 코드(`app/*`)의
      모든 함수 정의에 타입 힌트를 강제하도록 했다 - `tests/*`는
      테스트 함수마다 반환 타입(`-> None`)을 붙이는 관행이 이
      프로젝트에 없어서 제외했다(그대로 켰다면 426개 오류가 났을
      정도로 관행 차이가 큼). 이 옵션을 켜자마자 실제로 힌트가
      빠져 있던 함수 5개(`app/core/metrics.py`/`app/core/
      middleware.py`의 ASGI `send` 래퍼 3곳, `app/db/session.py`의
      SQLite PRAGMA 이벤트 리스너, `app/main.py`의 `lifespan`
      반환 타입)가 실제로 걸려서 전부 타입을 채웠다 - 이미 동작은
      맞았던 코드라 런타임 동작 변경은 없다. 다시 `app/core/
      cache.py`에 같은 재현 함수를 추가해 이번엔 mypy가 실제로
      막는지 재검증한 뒤 되돌렸다. 모델/스키마 변경이 아니라
      마이그레이션은 필요 없었다(`alembic check`로 드리프트 없음
      재확인).

## 백로그 (45라운드)

- [x] 69. CI 워크플로에 concurrency 취소 설정 누락 - 68번에 이어 계속
      훑다가 발견. 이 저장소는 로드맵 자동 개발 루프가 `claude/
      fastapi-architecture-improvements-pax3xs` 브랜치에 시간마다
      (때로는 한 시간 안에 여러 번) push하고, 그 브랜치는 이미 열려
      있는 PR #5에 반영되므로 매 push가 `pull_request`(synchronize)
      트리거로 `.github/workflows/ci.yml`의 세 job(test/migrations/
      secret-scan)을 전부 새로 돈다. `concurrency` 설정이 없어서
      과거 커밋에 대한 실행들이 취소되지 않고 끝까지(약 몇 분씩)
      돌아갔다 - 어차피 결과가 의미 있는 건 최신 커밋뿐인데 GitHub
      Actions 실행 분(minute)만 계속 낭비하는 구조였다. 워크플로
      최상단에 `concurrency: {group: "${{ github.workflow }}-${{
      github.ref }}", cancel-in-progress: true}`를 추가해서, 같은
      브랜치/PR에 새 push가 들어오면 그 ref에 진행 중이던 이전 실행을
      자동으로 취소하도록 했다. 코드 변경이 아니라 워크플로 설정
      파일만 바꾼 라운드라 앱 테스트/마이그레이션에는 영향이 없다 -
      YAML을 직접 파싱해 `concurrency` 블록과 기존 세 job이 모두
      그대로 남아있는지, mypy도 여전히 클린한지만 확인했다(GitHub
      Actions 실행 자체는 이 샌드박스에서 재현할 수 없어 설정값
      검증으로 범위를 좁혔다).

## 백로그 (46라운드)

- [x] 70. `docker-compose.yml`의 caddy 서비스에 healthcheck 누락 - 69번에
      이어 계속 훑다가 발견. `haruhan-backend`/`redis`/`prometheus`/
      `grafana`는 전부 `healthcheck`가 정의돼 있는데, 정작 80/443을
      호스트에 노출하는 유일한 실제 진입점인 `caddy`만 빠져 있었다 -
      Caddy 프로세스가 멈추거나(인증서 갱신 루프 등) `Caddyfile` 설정
      오류로 제대로 못 뜬 상태를 Docker/Compose가 감지할 방법이
      없었다(`restart: unless-stopped`는 컨테이너가 죽어야 재시작하지,
      떠 있는데 응답을 못 하는 상태는 못 잡는다). 외부 도메인/TLS
      인증서 발급 상태와 무관하게 항상 떠 있는 Caddy 관리 API
      (`localhost:2019`)를 `wget --spider`로 확인하도록 했다 - 실제
      사이트(`{$DOMAIN}`)를 체크 대상으로 삼으면 DNS/인증서 문제
      때문에 healthcheck가 실패해버려서 "Caddy 프로세스 자체는
      정상인데 사이트만 아직 준비 안 됨" 케이스와 "Caddy가 진짜 죽음"
      케이스를 구분할 수 없다. 다른 서비스와 같은 간격/타임아웃/
      재시도 값을 맞췄다. 코드 변경이 아니라 docker-compose 설정만
      바꾼 라운드라 앱 테스트는 영향이 없고, `docker compose config`
      로 파일이 유효하게 파싱되는지와 healthcheck 필드가 정확히
      들어갔는지 직접 확인했다(실제 컨테이너를 띄워보는 건 도메인/
      인증서가 필요해 이 샌드박스에서는 재현할 수 없었다).

## 백로그 (47라운드)

- [x] 71. PR #5의 `secret-scan`(gitleaks) CI 체크가 계속 실패하던 문제
      수정 - 이번엔 로드맵을 새로 훑기 전에 먼저 PR #5의 실제 CI/체크
      상태를 확인했다가 발견. `test`/`migrations`는 통과하는데
      `secret-scan`이 계속 실패 중이었다 - 로그를 보니 gitleaks가
      `docs/FRONTEND_INTEGRATION.md`의 로그인 응답 예시에 있는
      `refresh_token` 예시값(`"s24movQYshi-...`, 실제 발급된 토큰이
      아니라 프론트에게 응답 형태를 보여주려고 넣은 무작위 문자열)을
      엔트로피만 보고 `generic-api-key`로 오탐하고 있었다. 로컬에
      gitleaks 8.24.2를 직접 받아 재현(`detect --source=. --redact -v`
      → `leaks found: 1`, exit 1)한 뒤 원인을 확정했다. 이
      `secret-scan` job은 `fetch-depth: 0`으로 git 히스토리 전체를
      스캔하므로, 지금 파일 내용을 바꿔도 그 예시 문자열이 처음
      등장한 과거 커밋(`85c191d`)은 계속 스캔 대상이라 현재 파일을
      고치는 걸로는 해결이 안 된다 - `.gitleaksignore`에 gitleaks가
      출력한 정확한 fingerprint(`<commit>:<file>:<rule>:<line>`)를
      추가해 그 오탐 하나만 콕 집어 무시하도록 했다(다른 진짜 탐지는
      계속 잡혀야 하므로 규칙/파일 전체를 꺼버리는 대신 fingerprint
      단위로 좁혔다). 같은 gitleaks 바이너리로 재실행해
      `no leaks found`/exit 0으로 바뀌는 것까지 직접 확인했다. 같은
      PR에서 SonarCloud/GitGuardian도 실패 중인데, 이 둘은 이
      저장소의 `.github/workflows/*.yml`에 없는 외부 앱/대시보드
      기반 체크라 이 샌드박스에서는 원인 확인도(SonarCloud API가
      네트워크 프록시에 막힘) 재현도 할 수 없었다 - 손대지 않고
      사실만 남겨둔다. 모델/스키마/코드 변경이 아니라 마이그레이션은
      필요 없었다(`alembic check` 대상 아님).

## 백로그 (48라운드)

- [x] 72. GitGuardian 오탐 2건 조사 + 퀴즈 재제출 레이트리밋 누락 수정 -
      71번에서 고친 gitleaks 말고 GitGuardian도 실패 중이길래
      `get_check_run`으로 상세 내용을 직접 확인했다. "2 secrets"로
      잡힌 건 둘 다 실제 자격증명이 아니었다: (1) `.github/
      workflows/ci.yml`의 `POSTGRES_PASSWORD: postgres` - 62번에서
      추가한, CI 안에서만 잠깐 살아있는 일회용 Postgres 서비스
      컨테이너의 더미 비밀번호, (2) `tests/test_schemas_validators.py`
      의 `password="newsecret123"` - 63번 테스트에 쓴 순수 리터럴.
      GitGuardian은 gitleaks와 달리 정규식이 아니라 자체 서버가 값의
      해시(SHA)를 계산해 매칭하는 `secrets.ignored_matches` 방식이라,
      그 해시를 얻으려면 `ggshield secret scan`을 실제로 돌려야
      하는데 이건 GitGuardian API 키가 있어야 동작한다(로컬에 직접
      설치해 `ggshield secret scan path ...`로 확인함 - "API key가
      필요하다"며 거부됨). 이 샌드박스엔 그 키도, GitGuardian
      대시보드 접근권한도 없어 hash를 알아낼 방법이 없었고, 값 대신
      경로(`ignored_paths`) 단위로 무시하는 건 두 파일 다 이 자동
      루프가 계속 편집하는 파일이라 앞으로 진짜 시크릿이 섞여도 못
      잡게 되는 손실이 더 커서 하지 않았다 - 대신 두 GitGuardian
      incident 링크(36512156, 36512917)를 그대로 남겨서, 대시보드
      접근권한이 있는 사람이 "false positive"로 표시하면 바로
      해결되도록 해뒀다. 이 조사 과정에서 `/quizzes/{quiz_id}/submit`
      라우트를 다시 보다가 별개의 진짜 문제를 하나 더 발견했다 -
      이 라우트는 LLM을 호출하지 않지만(순수 채점), 재도전(다시 풀기)
      자체는 정상 기능이라 한도 없이 반복 제출되면 quiz_attempts/
      quiz_answers에 쓰기가 무제한으로 쌓일 수 있었다(67번에서 고친
      LLM 비용 증폭과 같은 종류의, "쓰기 증폭" 버전). 이 앱은
      auth_rate_limit(브루트포스용)/chat_rate_limit(의미 있는 상호
      작용용) 두 등급만 두고 있어서, 새 설정을 하나 더 만들기보다
      기존 quiz 생성/세션 생성 등과 같은 chat_rate_limit을 재사용해
      일관성을 유지했다. 기존 테스트 중 한 함수 안에서 `/submit`을
      최대 2번까지만 연속 호출해서(재도전 검증용) 기본값(분당
      10회)에 안전하게 들어간다는 것도 확인했다. `tests/test_quiz.py`
      에 존재하지 않는 quiz id로 반복 호출해도 레이트리밋이 걸리는지
      확인하는 테스트를 추가했고, `FRONTEND_INTEGRATION.md` 퀴즈
      제출 절에 이 제한을 안내하는 문장을 추가했다. 모델/스키마
      변경이 아니라 마이그레이션은 필요 없었다(`alembic check`로
      드리프트 없음 재확인).

## 백로그 (49라운드)

- [x] 73. `LOG_LEVEL`에 소문자/오타를 넣으면 불명확한 에러로 앱이
      죽던 문제 수정 - 72번에 이어 계속 훑다가 발견. `configure_logging()`
      이 `settings.log_level`을 그대로 `logging.basicConfig(level=...)`
      에 넘기는데, 파이썬 `logging` 모듈은 `"info"`처럼 소문자로 된
      레벨 이름을 받아들이지 않고 `ValueError: Unknown level: 'info'`
      를 던진다 - 직접 재현해서 확인했다(`.env.example`이 대문자를
      쓰라고는 안내하지만, 다른 도구들의 흔한 관례 때문에 소문자로
      적는 실수가 충분히 나올 수 있다). 이 호출은 `create_app()`
      안에서 이뤄지므로, `LOG_LEVEL`을 잘못 넣으면 서버 기동뿐 아니라
      **테스트를 돌릴 때마다** 이 불명확한 예외로 전부 실패한다.
      55번의 `jwt_secret_key` 검증과 같은 자리(`Settings`의
      `field_validator`)에 `log_level` 검증을 추가해서, 설정 로딩
      시점에 `DEBUG/INFO/WARNING/ERROR/CRITICAL` 중 하나인지
      확인하고 대문자로 정규화한다 - 그 외 값이면 어떤 값이 왜
      잘못됐는지 명확한 한국어 메시지로 바로 거부된다.
      `.env.example`에도 유효한 값과 대소문자 무관하다는 점을
      안내하는 주석을 추가했다. 사용자 대상 API 동작 변화가 없는
      설정 검증 전용 변경이라 `FRONTEND_INTEGRATION.md`는 갱신하지
      않았고, 모델/스키마 변경도 아니라 마이그레이션은 필요 없었다
      (`alembic check`로 드리프트 없음 재확인). `tests/test_config.py`
      에 소문자 정규화와 잘못된 값 거부를 검증하는 테스트를
      추가했다.

## 백로그 (50라운드)

- [x] 74. `ENVIRONMENT` 오타 시 프로덕션에서도 Swagger/ReDoc이 계속
      열려 있게 되던 fail-open 문제 수정 - 73번(LOG_LEVEL 검증)을
      끝내고 바로 옆에 있는 `environment` 필드도 같은 각도로 보다가
      발견. `app/main.py`가 `settings.environment == "production"`
      일 때만 `/docs`/`/redoc`/`/openapi.json`을 끄는데, 이 비교는
      정확히 소문자 `"production"`과 문자열이 완전히 같아야 참이
      된다 - `ENVIRONMENT=Production`(대문자 시작)이나 `prod`처럼
      흔히 실수할 수 있는 값을 넣으면 조용히 `False`가 되어, 실제
      운영 배포에서도 이 API의 유일한 실제 HTML 서빙 지점인 Swagger/
      ReDoc이 그대로 공개돼 있게 된다. 73번(LOG_LEVEL)이나 55번
      (JWT_SECRET_KEY)은 잘못 넣으면 앱이 못 뜨는(fail-closed) 쪽인
      반면, 이건 잘못 넣어도 앱이 멀쩡히 뜨면서 보안 기능만 조용히
      안 걸리는(fail-open) 훨씬 나쁜 실패 방향이라 더 시급하게
      막아야 할 케이스였다. `Settings`에 `_validate_environment`
      `field_validator`를 추가해 `development`/`production` 두
      값만(대소문자 무관, 정규화됨) 허용하고 그 외는 시작 시점에
      명확한 한국어 메시지로 거부하도록 했다. `tests/
      test_security_headers.py`가 이미 `ENVIRONMENT=production`
      (소문자)로 정확히 테스트하고 있어서 기존 동작에는 영향이
      없음을 재실행으로 확인했다. `.env.example`에도 유효한 값과
      오타 시 거부된다는 점을 안내하는 주석을 추가했다. 사용자
      대상 API 동작 변화가 없는 설정 검증 전용 변경이라
      `FRONTEND_INTEGRATION.md`는 갱신하지 않았고, 모델/스키마
      변경도 아니라 마이그레이션은 필요 없었다(`alembic check`로
      드리프트 없음 재확인). `tests/test_config.py`에 대소문자
      정규화와 잘못된 값(`prod`) 거부를 검증하는 테스트를
      추가했다.

## 백로그 (51라운드)

- [x] 75. Redis 장애 시 레이트리밋이 걸린 API 전체가 500으로 죽던
      치명적인 가용성 버그 수정 - 74번에서 설정 검증(fail-open) 각도로
      찾다가, "REDIS_URL이 가리키는 Redis가 응답을 못 하면 무슨 일이
      나는가"도 같은 각도라 직접 재현해봤다가 발견한 지금까지 중
      가장 파급 범위가 큰 문제였다. `app/core/rate_limit.py`의
      `Limiter`는 `storage_uri`에 지연 연결만 할 뿐 저장소 장애를
      스스로 처리하지 않는데, 이 앱은 auth/chat/quiz/interview 등
      거의 모든 쓰기 엔드포인트에 `@limiter.limit()`이 걸려 있다 -
      즉 Redis 하나가 재시작/네트워크 문제로 잠깐 응답을 못 하면,
      `redis.exceptions.ConnectionError`가 그대로 전역 예외
      핸들러까지 올라가 **그 엔드포인트들 전부**가 500을 반환하게
      된다(실제로 `REDIS_URL`을 닫힌 포트로 돌리고 `/auth/login`을
      호출해 500으로 죽는 것과, 존재하지 않는 세션 id에도 502가
      아니라 순수 커넥션 에러가 그대로 새는 것까지 직접 재현
      확인). Redis는 다중 워커/인스턴스 간 카운터 공유를 위한
      성능/정합성 개선 수단일 뿐인데, 정작 죽으면 API 자체가
      멎어버려 "레이트리밋"이라는 부가 기능이 핵심 기능의 단일
      장애점이 되어 있었다. slowapi `Limiter`가 이미 제공하는
      `in_memory_fallback_enabled=True`를 켜서, 저장소 장애를
      감지한 시점부터 자동으로 프로세스 내 메모리 카운터로
      전환하고(여러 워커 간 정확도는 떨어지지만 무방비보다 훨씬
      낫다) Redis가 살아나면 자동 복귀하도록 했다 - `@limiter.
      limit()` 데코레이터 경로는 이걸로 해결된다. 다만 WebSocket
      경로에서 쓰는 `check_rate_limit()`은 `limiter.limiter`(내부
      저장소 전략 객체)를 직접 호출해서 이 자동 복구 로직을 안
      거치므로 별도로 `RedisError`를 잡아 "허용"으로 처리하도록
      고쳤다(레이트리밋보다 서비스 가용성이 우선이라는 원칙을
      명시적으로 한 곳에 더 적용). `tests/test_rate_limit_redis.py`
      에 실제 존재하지 않는 포트로 Limiter를 만들어 HTTP 라우트가
      500 없이 정상 응답하는지, `check_rate_limit()`이 예외 대신
      허용을 반환하는지 둘 다 검증하는 테스트를 추가해 100% 커버리지로
      확인했다. 모델/스키마 변경이 아니라 마이그레이션은 필요
      없었다(`alembic check`로 드리프트 없음 재확인).

## 백로그 (52라운드)

- [x] 76. Ollama가 200과 함께 JSON 아닌 본문을 주면 `OllamaServiceError`
      로 안 묶이던 문제 수정 - 75번(Redis 장애 시 예외가 안 잡히는
      경로)과 같은 각도를 다른 외부 의존성(Ollama)에도 적용해보다가
      발견. `app/services/ollama_service.py`의 `generate`/`chat`/
      `embed`/`list_models`/`generate_json` 다섯 메서드 모두
      `response.json()` 호출이 `try: ... except httpx.HTTPError`
      블록 **바깥**에 있었다 - HTTP 상태 코드 에러는 전부
      `OllamaServiceError`로 통일해서 잡지만, Ollama 앞단 프록시
      오작동이나 응답이 중간에 끊기는 경우처럼 상태 코드는 200인데
      본문이 JSON이 아닌 경우는 `json.JSONDecodeError`가 그대로
      새어나가 이 서비스의 나머지 실패 경로(어디서 호출하든
      `except OllamaServiceError`로 깔끔하게 502/500 처리됨)와
      다르게 처리되지 않은 예외로 상위까지 올라간다. `chat_stream`도
      스트리밍 줄 단위 `json.loads(line)`이 try 블록 안에는
      있었지만 `except`가 `httpx.HTTPError`만 잡고 있어 같은
      문제가 있었다. httpx `MockTransport`로 상태 200 + 본문
      `b"not json"`을 주는 가짜 Ollama를 만들어 다섯 메서드 전부에서
      `JSONDecodeError`가 그대로 새는 것을 먼저 재현 확인한 뒤,
      `response.json()` 호출을 try 블록 안으로 옮기고
      `except (httpx.HTTPError, json.JSONDecodeError)`로 넓혀서
      한 곳에서 통일되게 처리하도록 고쳤다. `tests/
      test_ollama_service.py`에 여섯 메서드(`chat_stream` 포함)
      전부 이 케이스에서 `OllamaServiceError`로 정리되는지 검증하는
      테스트를 추가했다 - 덕분에 이전까지 "테스트하기 어려운 네트워크
      래퍼"라 커버리지를 일부러 안 쫓기로 했던(38라운드 이전 결정)
      `ollama_service.py`의 커버리지도 75%에서 92%로 함께 올라갔다.
      모델/스키마 변경이 아니라 마이그레이션은 필요 없었다
      (`alembic check`로 드리프트 없음 재확인).

## 백로그 (53라운드)

- [x] 77. 이메일 중복 가입/변경 경쟁 상태에서 500이 나던 문제 수정 -
      75/76번과 같은 "외부 의존성이 예상 못 한 방식으로 실패하면
      어떻게 되는가" 각도를 세 번째 외부 의존성인 DB 자체(정확히는
      DB의 unique 제약)에도 적용해보다가 발견. `signup()`/
      `upgrade_guest()`/`update_profile()`(이메일 변경 시) 셋 다
      `get_by_email`로 "존재 안 함"을 먼저 확인한 뒤에야 insert/
      update한다(check-then-act) - 같은 이메일로 거의 동시에 두
      요청이 오면 둘 다 그 확인을 통과해버릴 수 있다. `User.email`
      의 DB unique 제약이 최종 방어선으로 남아있어 데이터가 잘못
      들어가진 않지만, 그 위반이 `sqlalchemy.exc.IntegrityError`로
      그대로 새어나가면 정상적인(경쟁 없는) "이미 존재함" 케이스는
      깔끔한 409인데 경쟁이 실제로 발생한 케이스만 처리되지 않은
      예외로 500이 되는 비일관성이 있었다. 파일 기반 SQLite에
      진짜 별개의 커넥션 두 개를 만들고 `asyncio.gather`로 같은
      이메일을 향한 두 서비스 호출을 동시에 실행해 세 메서드
      전부에서 재현 확인(`sqlite3.IntegrityError: UNIQUE constraint
      failed`)한 뒤, 각 메서드의 commit을 `try/except IntegrityError`
      로 감싸 롤백 후 기존과 동일한 409 `HTTPException`으로
      변환하도록 고쳤다 - 프론트 입장에서 보이는 응답 계약(중복
      이메일은 409)은 그대로고, 경쟁 상태에서만 어겨지던 걸 바로
      잡은 것이다. `signup()`은 `UserRepository.create()`가 즉시
      `flush()`하므로 그 호출 자체를 try에 넣었고, 나머지 둘은
      속성 변경 후 최종 `commit()` 시점에만 flush가 일어나므로
      그 commit만 감쌌다. `tests/test_auth.py`/`test_guest_auth.py`/
      `test_users.py`에 각각 파일 기반 SQLite + `asyncio.gather`로
      실제 경쟁을 재현해 "하나는 성공, 하나는 깔끔한 409, 그 외
      처리 안 된 예외는 없음"을 검증하는 테스트를 추가했다(5회
      반복 실행으로 재현 안정성도 확인). `auth_service.py`/
      `user_service.py` 둘 다 새 브랜치가 100% 커버리지로 잡혔다.
      모델/스키마 변경이 아니라 마이그레이션은 필요 없었다
      (`alembic check`로 드리프트 없음 재확인).

## 백로그 (54라운드)

- [x] 78. 면접 연습 답변 제출 경쟁 상태에서 답변이 조용히 사라지고
      중복 턴이 생기던 문제 수정 - 77번과 같은 "check-then-act
      경쟁 상태" 렌즈를 면접 연습에도 적용해보다가, 이번엔 unique
      제약으로 막히는 크래시가 아니라 **데이터가 조용히 사라지는**
      더 심각한 버전을 발견했다. `submit_answer()`는 "현재 턴이
      미답변 상태인가"를 읽은 뒤 AI 호출 결과를 `current_turn.answer
      = answer`로 그냥 대입하고 커밋한다 - 같은 질문에 답변이 두 번
      거의 동시에 제출되면(이중 클릭, 네트워크 재시도) 둘 다 "미답변"
      을 보고 통과해서 각자 AI 응답을 계산해 쓴다. 파일 기반 SQLite에
      진짜 별개의 커넥션 두 개를 만들어 `asyncio.gather`로 재현한
      결과, **나중에 커밋된 쪽이 먼저 쪽의 답변/피드백을 조용히
      덮어썼고**(lost update), 다음 질문 턴도 같은 `order_index`로
      두 개 중복 생성됐다 - 둘 다 200을 받았고 어느 쪽도 에러를
      몰랐다. `interview_practice_turns`에 unique 제약을 추가하는
      방식(77번과 같은 패턴)도 고려했지만, 그 방식은 새 턴 INSERT
      충돌만 잡을 뿐 기존 턴의 answer/feedback UPDATE 자체를 막지는
      못해 절반만 고쳐진다는 걸 직접 재현으로 확인하고 기각했다.
      대신 `InterviewPracticeTurnRepository`에 `mark_answered_if_pending()`
      compare-and-swap을 추가했다 - `WHERE answer IS NULL` 조건을 건
      UPDATE로, 이미 누군가 먼저 답변을 기록했다면 이 UPDATE는 영향받는
      행이 0개가 되어 "이미 늦음"을 알 수 있다. `submit_answer()`의
      두 분기(다음 질문 생성/마지막 피드백) 모두에서 기존 직접 대입을
      이 CAS 호출로 바꾸고, 실패하면(늦게 도착한 쪽) 다음 턴을 만들지
      않고 기존에도 있던 `_NO_PENDING_QUESTION`(409, "답변할 질문이
      없습니다")으로 정리하도록 했다 - 새로운 응답 코드를 만들 필요
      없이 기존 "이미 답변됨" 케이스와 같은 의미로 자연스럽게
      합쳐졌다. 같은 재현 스크립트로 수정 후에는 승자의 답변만 남고
      중복 턴 없이 정확히 깔끔한 409가 나는 것까지 확인했다. 진짜
      동시성 재현은 SQLite 파일 락 모델이 두 커넥션의 읽기→쓰기
      전이 시점에서 너무 불안정하게 실패해서(재현 자체가 아니라
      테스트 인프라 문제), 대신 `mark_answered_if_pending()`을 직접
      두 번 호출해 승자/패자를 결정적으로 검증하는 테스트와, 가짜
      Ollama 서비스가 응답 직전에 "동시 요청"을 주입하도록 만들어
      `submit_answer()`의 두 분기 모두에서 타이밍을 결정적으로
      재현하는 테스트를 추가했다. `interview_practice_service.py`가
      100% 커버리지로 확인됐다. 모델/스키마 변경이 아니라
      마이그레이션은 필요 없었다(`alembic check`로 드리프트 없음
      재확인).

## 백로그 (55라운드)

- [x] 79. CI의 pip-audit이 requirements-dev.txt는 감사하지 않던 구멍
      수정 - 78번까지 애플리케이션/동시성 버그를 계속 찾다가, 이번엔
      CI 설정 자체를 다시 훑어보다가 발견. `.github/workflows/ci.yml`
      의 `pip-audit -r requirements.txt`는 운영에 실제로 배포되는
      의존성만 감사하고, `requirements-dev.txt`가 추가로 얹는 CI/
      개발 전용 패키지(pytest, mypy, pip-audit 자기 자신, aiosqlite
      등)는 감사 대상에서 아예 빠져 있었다 - 이 패키지들은 운영에
      배포되진 않지만, CI 실행 환경 자체가 알려진 취약점이 있는
      도구로 빌드/테스트를 도는 것도 공급망 관점에서 확인할 가치가
      있다. `test` job에 `pip-audit -r requirements-dev.txt` 단계를
      추가했다. 로컬에서 `pip-audit -r requirements.txt`/
      `pip-audit -r requirements-dev.txt` 둘 다 직접 재실행해 현재는
      알려진 취약점이 없음을 확인했고, YAML을 파싱해 새 step이
      올바른 위치에 정확히 들어갔는지도 확인했다. 코드 변경이
      아니라 워크플로 설정만 바꾼 라운드라 앱 테스트/마이그레이션에는
      영향이 없고, mypy도 여전히 클린함을 재확인했다.

## 백로그 (56라운드)

- [x] 80. WebSocket 메시지 크기가 HTTP 요청 본문 제한보다 16배 더
      관대하던 문제 수정 - HTTP는 `MaxBodySizeMiddleware`(기본
      `MAX_BODY_SIZE_BYTES=1MiB`)로 요청 본문 크기를 명시적으로
      막아두고 있는데, 같은 스트리밍 기능을 제공하는 WebSocket
      경로(학습챗/면접복기 `/stream`)는 이 미들웨어를 아예 거치지
      않고 uvicorn의 기본값(`ws_max_size=16MiB`)을 그대로 쓰고
      있었다 - 아무도 의도적으로 정한 적 없는 값인데, 실제 메시지
      크기 기대치(`max_prompt_length` 4000자, `max_review_content_
      length` 10000자)보다 수백 배 관대해서 WS 쪽만 유독 대용량
      메시지를 통한 메모리 소모형 DoS에 취약했다. 직접 uvicorn
      서버를 띄우고 `websockets` 클라이언트로 2MiB 메시지를 보내
      재현했다 - 기본값으로는 그대로 통과해 처리되고, `--ws-max-
      size=1048576`을 켜면 프로토콜 레벨에서 `1009 message too
      big`으로 거부되는 것까지 양쪽 다 직접 확인했다. `Dockerfile`
      의 uvicorn CMD에 이 플래그를 추가해 HTTP 쪽 기본값과 같은
      1MiB로 두 경로의 보호 수준을 통일했다. `MAX_BODY_SIZE_BYTES`
      처럼 런타임에 읽는 앱 설정이 아니라 uvicorn 시작 시점의 고정
      플래그라 실제 env var 값과 자동으로 동기화되진 않는다는 점은
      59번(`--proxy-headers`)과 같은 성격의 한계로 남겨뒀다.
      `tests/test_dockerfile.py`에 이 플래그가 CMD에서 조용히
      빠지는 회귀를 막는 테스트를 추가했다(59번 때 확립한 패턴과
      동일). 코드 변경이 아니라 Dockerfile/uvicorn 실행 옵션만
      바꾼 라운드라 앱 테스트에는 영향이 없고, 모델/스키마 변경도
      아니라 마이그레이션은 필요 없었다(`alembic check`로 드리프트
      없음 재확인).

## 백로그 (57라운드)

- [x] 81. `OllamaService`가 메서드 호출마다 새 `httpx.AsyncClient`를
      만들어 커넥션을 매번 새로 맺던 비효율 수정 - `generate`/
      `chat`/`chat_stream`/`embed`/`list_models`/`generate_json`
      여섯 메서드 전부가 각자 `async with httpx.AsyncClient(...)`로
      자기 것만 만들어 쓰고 버리고 있었다 - Ollama 호출 하나당 TCP
      연결을 새로 맺고 끊는 셈이라, 학습챗 스트리밍처럼 한 요청 안에
      RAG 임베딩(`embed`) + 답변 생성(`chat_stream`)을 연달아 호출하는
      경로에서는 같은 대상(같은 Ollama 엔진)에 커넥션을 계속 새로
      여는 낭비가 있었다. `OllamaService.__init__`에서 `httpx.
      AsyncClient` 하나를 만들어 인스턴스 수명 동안 재사용하도록
      바꾸고(`aclose()` 추가), `core/dependencies.py`의
      `get_ollama_service`를 일반 함수에서 `yield` 기반 제너레이터
      의존성으로 바꿔서 요청/WebSocket 연결이 끝나면 자동으로
      `aclose()`가 호출되도록 했다 - FastAPI의 의존성 캐싱 덕분에
      한 요청 안에서 여러 서비스가 `Depends(get_ollama_service)`를
      거쳐도 같은 인스턴스(=같은 커넥션)를 공유한다. 직접 DI를
      안 거치고 `OllamaService`를 만드는 두 곳(`rag_backfill_
      service.py`의 스케줄러 job, `scripts/backfill_knowledge_
      chunks.py`의 수동 백필 스크립트)도 각각 `finally`에서
      `aclose()`를 호출하도록 맞췄다. 같은 인스턴스가 여러 호출에서
      정말 같은 클라이언트 객체를 재사용하는지, `aclose()` 후
      `client.is_closed`가 실제로 `True`가 되는지 직접 스크립트로
      확인했다. 기존 `tests/test_ollama_service.py`의 `httpx.
      AsyncClient.__init__`을 몽키패치하는 방식이 생성자 호출
      시점과 무관하게 그대로 통했다(15개 테스트 전부 통과). 코드
      동작(응답 내용)은 그대로라 사용자 대상 API 변경이나 문서
      갱신은 필요 없었고, 모델/스키마 변경도 아니라 마이그레이션은
      필요 없었다(`alembic check`로 드리프트 없음 재확인).

## 백로그 (58라운드)

- [x] 82. `get_ollama_service`의 WebSocket 연결 정리(cleanup) 경로에
      실제 검증이 없던 구멍 수정 - 81번에서 `get_ollama_service`를
      `yield` 기반 제너레이터 의존성으로 바꿔 요청/WebSocket 연결이
      끝나면 `finally`에서 `aclose()`가 자동 호출되도록 했는데,
      정작 `tests/test_study.py`의 기존 WebSocket 테스트들은 전부
      `dependency_overrides[get_ollama_service] = lambda: Fake...()`
      처럼 일반 함수로 오버라이드하고 있었다 - 이러면 FastAPI가
      실제 의존성을 아예 안 거치고 오버라이드한 값을 바로 쓰므로,
      이 제너레이터의 `finally` 블록(=WS 연결 종료 시 자동 정리)
      자체가 어느 테스트로도 실행되지 않는 채로 81번이 머지될
      뻔했다. 먼저 임시 검증 스크립트로 실제 `TestClient.
      websocket_connect(...)`를 열었다 닫아서 FastAPI의 제너레이터
      의존성 정리가 WebSocket 연결 종료 시에도 정상 동작함을
      확인한 뒤(HTTP 요청뿐 아니라 WS 연결 해제(disconnect) 시에도
      `finally`가 실행됨), 이 확인을 `tests/test_study.py`에 영구
      회귀 테스트로 남겼다 - `get_ollama_service`와 동일하게
      `yield`/`finally` 구조를 갖는 `tracked_get_ollama_service`로
      오버라이드해, 스트리밍 WebSocket이 정상 종료된 뒤 `aclose()`
      가 실제로 호출됐는지 플래그로 확인한다(이 테스트를 일부러
      되돌려서 `finally`를 지워보면 실패하는 것도 확인). 새 버그를
      고친 게 아니라 81번의 수정이 WS 경로에서도 실제로 유효함을
      증명하는 회귀 방지 테스트라 사용자 대상 동작 변경이나 문서
      갱신은 필요 없었고, 모델/스키마 변경도 아니라 마이그레이션은
      필요 없었다(테스트만 추가된 라운드라 `alembic check`는 재확인
      대상이 아니지만, mypy와 전체 테스트는 그대로 재실행해 클린함을
      확인했다).

## 백로그 (59라운드)

- [x] 83. refresh token 로테이션에도 있던 check-then-act 경쟁으로
      토큰 재사용 탐지가 무력화될 수 있던 문제 수정 - `AuthService.
      refresh()`는 "제시된 토큰이 아직 안 폐기됐는가"를 확인한
      뒤에야 그 토큰을 폐기하고 새 토큰 쌍을 발급하는 구조였다.
      53번(회원가입)·78번(면접 답변 제출)에서 고친 것과 같은
      계열의 경쟁 상태가 여기도 그대로 있었다 - 같은 refresh
      token으로 거의 동시에 두 요청이 오면(탈취범이 훔친 토큰을
      정상 사용자와 동시에 쓰는 경우 등) 둘 다 "아직 안 폐기됨"을
      확인하고 통과해버릴 수 있는데, 이전 구현은 그 뒤 그냥
      `UPDATE`로 폐기했으므로 둘 다 폐기에 성공해 하나의 토큰
      소비로 두 개의 유효한 세션이 나올 수 있었다 - 이 로테이션/
      재사용 탐지 메커니즘이 애초에 막으려던 상황(탈취된 토큰의
      병행 사용)을 오히려 통과시켜버리는 셈이라 78번·53번보다도
      보안적으로 더 무거운 결함이었다. `RefreshTokenRepository`에
      `WHERE revoked_at IS NULL`을 건 원자적 UPDATE인
      `revoke_if_active()`(compare-and-swap)를 추가하고, `refresh()`
      가 이걸 써서 폐기에 실패하면(=경쟁에서 짐) 이미 재사용된
      토큰을 만난 것과 동일하게 처리하도록(해당 유저의 모든 활성
      세션 강제 로그아웃 + 401) 바꿨다. 진짜 `asyncio.gather` 동시
      재현은 이 흐름이 폐기(UPDATE) + 발급(INSERT) + 커밋까지
      여러 단계를 거치는 다중 쓰기 트랜잭션이라 54번에서 이미 겪은
      것과 같은 이유로 SQLite 파일 락 모델에서 결정적이지 않을 걸로
      판단해, 54번 때 정립한 대안을 그대로 따랐다 - (1) `revoke_
      if_active()`를 같은 토큰에 순서대로 두 번 호출해 첫 번째만
      성공(True)/두 번째는 실패(False)함을 직접 검증하는 테스트,
      (2) 같은 토큰으로 "동시에" 온 다른 요청이 이미 폐기 +
      로테이션까지 끝낸 상황을 `revoke_if_active` 호출 지점에
      결정적으로 주입해, 패자가 401을 받고 승자가 방금 발급받은
      최신 토큰까지 포함해 그 유저의 모든 세션이 강제로 끊기는지
      확인하는 테스트. 두 테스트 모두 수정 전 코드로 되돌려서
      실제로 실패하는 것까지 확인한 뒤 다시 적용했다. 응답 형태
      (성공 시 새 토큰 쌍, 재사용 시 401)는 이전과 동일해 사용자
      대상 문서 갱신은 필요 없었고, 모델/스키마 변경도 아니라
      마이그레이션은 필요 없었다(`alembic check`로 드리프트 없음
      재확인).

## 백로그 (60라운드)

- [x] 84. 학습챗이 매 메시지마다 세션의 전체 대화 히스토리를 그대로
      Ollama 프롬프트에 다시 실어 보내던 문제 수정 - `StudyService.
      send_message`/`stream_message`는 그 세션에 지금까지 쌓인
      메시지 전부를 매번 다시 프롬프트에 포함시켰다. 면접연습은
      `max_interview_questions`(기본 5)로 세션당 질문 수 자체가
      작게 제한돼 있어 이 문제가 없었지만, 학습챗 세션은 메시지 수
      제한이 아예 없다 - 사용자가 한 세션에서 대화를 길게 이어갈수록
      한 번의 Ollama 호출에 실리는 토큰 수가 무한정 늘어나서,
      언젠가 로컬 모델의 컨텍스트 윈도우를 넘기면 앞부분이 조용히
      잘리거나(모델/런타임에 따라 무엇이 잘릴지 예측 불가) 응답
      품질이 떨어지고 지연/리소스 사용량도 계속 커지는 구조였다.
      새 설정 `max_chat_history_messages`(기본 40)를 추가하고,
      `StudyService`에 `settings`를 주입해 프롬프트를 만들기 전에
      가장 최근 이 개수만큼의 메시지만 남기도록 잘라내는 `_recent_
      history()` 헬퍼를 두 경로(REST/WebSocket) 모두에 적용했다 -
      DB에 저장되는 전체 히스토리 자체(`GET /study/sessions/{id}`
      로 조회되는 것)는 그대로 다 남고, AI에게 보내는 컨텍스트만
      최근 것으로 제한된다. 구현 중 파이썬 슬라이싱의 함정도 하나
      잡았다 - `history[-0:]`은 (음수 0이 없어서) 빈 리스트가 아니라
      `history[0:]`, 즉 전체 리스트가 되어버려서 "0이면 히스토리
      없이 보내라"는 의도가 조용히 뒤집힐 뻔했다 - 0/음수를 명시적
      으로 빈 리스트로 처리하는 단위 테스트를 따로 추가해 이 함정
      자체를 검증해뒀다. REST/WebSocket 두 경로 모두 히스토리가
      실제로 설정값만큼만 잘려서 전달되는지 확인하는 회귀 테스트를
      추가했고(수정 전 코드로 되돌려 두 테스트가 실제로 실패하는
      것도 확인), `study_service.py`는 새 테스트들로 100% 커버리지를
      유지한다. AI가 아주 긴 대화에서 훨씬 이전 내용을 더 이상
      "기억"하지 못할 수 있다는 건 사용자에게 보이는 동작 변화라
      `FRONTEND_INTEGRATION.md`에 설명을 추가했다. 모델/스키마
      변경은 아니라 마이그레이션은 필요 없었다(`alembic check`로
      드리프트 없음 재확인).

## 백로그 (61라운드)

- [x] 85. 오답노트(`GET /quizzes/wrong-answers`) 조회가 퀴즈 개수만큼
      쿼리가 느는 N+1 패턴이던 문제 수정 - `QuizService.
      get_wrong_answer_notebook()`은 사용자의 퀴즈 목록을 파이썬으로
      순회하면서 퀴즈마다 "최근 제출 조회"/"그 제출의 답안 조회"/
      "문항 목록 조회"를 따로 날렸다 - 퀴즈가 N개면 최대 1+3N번의
      쿼리가 나가는 구조였다. 42번(RAG 백필)에서 고친 것과 같은
      계열의 문제라, 이번엔 "퀴즈별 최신 제출"이라는 그룹별 top-1
      조건이 있어서 단순 LEFT JOIN이 아니라 윈도우 함수(`ROW_NUMBER()
      OVER (PARTITION BY quiz_id ORDER BY submitted_at DESC)`)로
      퀴즈별 최신 제출을 한 번에 골라낸 뒤, 그 제출의 오답만
      Quiz/QuizQuestion과 조인해 쿼리 하나로 가져오도록 바꿨다 -
      SQLite/Postgres 둘 다 지원하는 표준 SQL이라 두 환경에서 동일하게
      동작한다. 기존 오답노트 테스트(최근 제출 기준 필터링, 재도전
      시 맞힌 문제 제외, 시도 없는 퀴즈 제외 등)가 전부 그대로
      통과해 동작 자체는 바뀌지 않았음을 확인했고, 이번 회귀가
      재발하지 않도록 SQLAlchemy의 `before_cursor_execute` 이벤트로
      실행되는 SELECT 문 개수를 직접 세는 테스트를 새로 추가했다 -
      퀴즈 5개에 각각 오답이 있어도 SELECT가 정확히 1번만 나가는지
      확인하며, 수정 전 코드로 되돌려 실제로는 16번(1+3×5) 나가서
      이 테스트가 실패하는 것까지 확인한 뒤 다시 적용했다.
      `quiz_service.py`는 새 테스트로 100% 커버리지를 유지한다.
      응답 형태는 이전과 동일해 사용자 대상 문서 갱신은 필요 없었고,
      모델/스키마 변경도 아니라 마이그레이션은 필요 없었다(`alembic
      check`로 드리프트 없음 재확인).

## 백로그 (62라운드)

- [x] 86. 데이터 export(`GET /export/me`)가 학습챗 세션/퀴즈/시도/면접연습
      세션 개수만큼 쿼리가 느는 N+1 패턴이던 문제 수정 - 61번(오답노트)과
      같은 계열의 문제를 `ExportService`에서도 찾았다. `_build_study_
      sessions`는 세션마다 메시지 조회를, `_build_quizzes`는 퀴즈마다
      문항 조회 + 시도마다 답안 조회를, `_build_practice_sessions`는
      세션마다 턴 조회를 따로 날렸다 - 계정을 오래 쓸수록 세션/퀴즈/
      시도 수가 계속 늘어나는데, "내 데이터 전체 내려받기"라는 기능
      특성상 매번 그 전체 규모만큼 쿼리가 나가는 셈이었다. 오답노트와
      달리 여기는 "그룹별 top-1"이 아니라 "그룹별 전체 자식"이 필요해서
      윈도우 함수 대신, 각 자식 테이블에 `WHERE parent_id IN (...)`로
      한 번에 다 가져온 뒤 파이썬에서 부모 id별로 다시 묶는 방식을
      택했다 - `StudyMessageRepository.list_for_sessions`, `QuizQuestion
      Repository.list_for_quizzes`, `QuizAnswerRepository.list_for_
      attempts`, `InterviewPracticeTurnRepository.list_for_sessions`
      네 개의 배치 조회 메서드를 추가했다. 이런 "여러 부모의 자식을
      한 번에 가져와 파이썬에서 다시 묶기" 리팩터링에서 가장 위험한
      실수는 묶는 키를 잘못 써서 다른 세션/퀴즈/시도의 자식이 섞여
      들어가는 것이라, 학습챗 세션 2개·퀴즈 2개(각 재도전 포함)·
      면접연습 세션 2개를 만들어 각 항목의 자식이 정확히 자기 것끼리만
      묶이는지 id 기준으로 확인하는 테스트를 추가했다 - 부모 id 대신
      고정값으로 묶도록 일부러 망가뜨려서 이 테스트가 실제로 실패하는
      것도 확인했고, 반대로 이전(N+1) 구현으로 되돌려도 이 테스트가
      여전히 통과함을 확인해 이번 리팩터링이 순수 성능 개선이고 결과는
      바뀌지 않았음을 검증했다. `export_service.py`와 관련 리포지토리
      전부 새 테스트로 100% 커버리지를 유지한다. 응답 형태는 이전과
      동일해 사용자 대상 문서 갱신은 필요 없었고, 모델/스키마 변경도
      아니라 마이그레이션은 필요 없었다(`alembic check`로 드리프트
      없음 재확인).

## 백로그 (63라운드)

- [x] 87. 방치된 WebSocket 연결이 DB 커넥션 풀을 고갈시킬 수 있던 문제
      수정 - 학습챗/면접복기 스트리밍(`/study/sessions/{id}/stream`,
      `/interview/reviews/stream`)은 `get_db`/`get_ollama_service`
      의존성이 연결이 살아있는 동안 DB 커넥션 풀의 커넥션 하나와
      Ollama httpx 클라이언트를 계속 붙잡고 있는 구조다. 두 핸들러
      모두 `while True: payload = await websocket.receive_json()`로
      클라이언트 메시지를 기다리는데, 이 대기에 타임아웃이 전혀 없어서
      클라이언트가 연결만 해두고 메시지를 영영 안 보내면(느린 네트워크,
      방치된 탭, 혹은 의도적 남용) 그 자원이 무한정 잠긴다 - DB
      엔진의 기본 풀 크기(`pool_size=5 + max_overflow=5 = 10`)보다도
      적은 수의 이런 idle 연결만으로 풀 전체가 고갈되어 앱 전체(다른
      모든 HTTP/WS 요청)가 막힐 수 있는, 낮은 진입장벽의 DoS였다.
      새 설정 `ws_idle_timeout_seconds`(기본 300초)를 추가하고,
      `websocket.receive_json()`을 `asyncio.wait_for(...)`로 감싸
      타임아웃이 나면 정상 종료 코드(1000)로 연결을 끊도록 두 경로
      모두 고쳤다. 두 라우트 모두 타임아웃 값을 아주 짧게(0.05초)
      줄여서 실제로 메시지를 하나도 안 보내도 서버가 먼저 연결을
      끊는지 확인하는 테스트를 추가했다 - 수정 전 코드로는 이 테스트가
      통과는커녕 `receive_json()`이 영원히 안 끝나서 테스트 자체가
      멈춰버리는 것까지 직접 재현해 문제의 심각성을 재확인한 뒤 다시
      적용했다. `study.py`/`interview_review.py` 라우트 모두 새
      테스트로 100% 커버리지를 유지한다. 정상적으로 대화를 이어가는
      사용자에게는 영향이 없지만, 탭을 오래 켜두고 방치하면 연결이
      끊길 수 있다는 사용자 대상 동작 변화라 `FRONTEND_INTEGRATION.md`
      에 재연결 안내를 추가했다. 모델/스키마 변경은 아니라 마이그레이션은
      필요 없었다(`alembic check`로 드리프트 없음 재확인).

## 백로그 (64라운드)

- [x] 88. 운영 배포의 모든 응답이 압축 없이 나가던 문제 수정 - 리버스
      프록시로 쓰는 `Caddyfile`이 `reverse_proxy` 지시어만 있고 압축
      관련 설정이 전혀 없었다. nginx는 gzip을 기본으로 켜주는 경우가
      많아 흔히 당연하게 여기지만, Caddy는 `encode` 지시어를 명시적으로
      넣지 않으면 압축을 전혀 하지 않는다 - 그래서 학습챗 세션 상세
      (메시지 히스토리 전체 포함)나 데이터 export(`GET /export/me`,
      계정이 오래될수록 커짐)처럼 커질 수 있는 JSON 응답도 전부 압축
      없이 그대로 나가고 있었다. `Caddyfile`에 `encode zstd gzip`을
      추가했다 - WebSocket 업그레이드 응답처럼 본문이 없는 응답이나
      이미 압축된 타입은 Caddy가 알아서 건너뛰므로 스트리밍 경로에는
      영향이 없다. 애플리케이션 코드가 아니라 배포 설정 파일이라
      `tests/test_dockerfile.py`(59/80번 라운드에서 확립한, 정적 설정
      파일을 텍스트로 읽어 특정 지시어/플래그가 조용히 빠지는 회귀를
      막는 패턴)와 같은 방식으로 `tests/test_caddyfile.py`를 새로
      추가해 `encode` 지시어가 있는지 확인한다 - 수정 전 파일로
      되돌리면 이 테스트가 실제로 실패하는 것도 확인했다. 압축은
      HTTP 클라이언트(브라우저/fetch)가 `Content-Encoding`을 자동으로
      처리하므로 프론트 쪽 코드 변경이나 문서 갱신은 필요 없었고,
      Python 코드/모델 변경이 전혀 없는 라운드라 마이그레이션도 해당
      없다.

## 백로그 (65라운드)

- [x] 89. 실제 Ollama 스트리밍 클라이언트(`OllamaService.chat_stream`)의
      정상 동작 경로가 테스트 스위트 전체에서 한 번도 검증되지 않고
      있던 커버리지 구멍 수정 - 커버리지 리포트를 다시 훑어보다가
      `ollama_service.py`의 `chat_stream()` 본문(ndjson 줄 파싱,
      빈 줄 건너뛰기, content 추출/yield, `done`에서 멈추기)이 전부
      미실행으로 잡혀 있는 걸 발견했다. 원인은 `tests/test_ollama_
      service.py`에 이 메서드용 테스트가 malformed-JSON 에러 경로
      하나뿐이었고, study/interview-review 스트리밍 라우트 테스트들은
      전부 `FakeOllamaService`로 이 메서드 자체를 통째로 갈아치워서
      실제 구현이 어디서도 실행되지 않았기 때문이다 - 즉 실제 운영
      환경에서 Ollama와 통신하는 이 파싱 로직에 회귀가 생겨도(예:
      `done` 처리가 깨져 스트림이 멈추지 않거나, 빈 줄 처리가 깨져
      크래시하거나) 319개 테스트 중 어느 것도 잡아내지 못하는 상태
      였다. 실제 Ollama가 보내는 형태(줄 사이 빈 줄, `done: true`인
      마지막 줄은 content가 비어있음)를 흉내 낸 ndjson 스트림으로
      정상 동작 테스트를 추가했다 - 처음엔 `done` 이후에 오는 줄을
      스트림에 안 넣어서 `break`를 지워도 테스트가 통과해버리는
      허술한 테스트였는데, `done` 이후에도 content가 있는 줄을 하나
      더 흘려보내도록 고쳐서 `break`를 실제로 지워보면 그 내용까지
      결과에 섞여 들어와 테스트가 제대로 실패하는 것까지 확인한 뒤
      최종 버전을 적용했다. `ollama_service.py`는 이제 100% 커버리지
      (기존 미실행 6줄 전부 해소, 전체 커버리지도 99%대에서 미실행
      2줄까지로 줄었다). 테스트만 추가된 라운드라 프로덕션 코드/모델
      변경이 없어 문서 갱신이나 마이그레이션은 해당 없다.

## 백로그 (66라운드)

- [x] 90. `.dockerignore`가 실제 가상환경 디렉터리명과 달라서 매 Docker
      빌드마다 수백 MB가 불필요하게 빌드 컨텍스트로 전송되던 문제 수정 -
      63/64번(WS idle timeout, Caddy 압축)에 이어 다시 배포 설정을
      훑어보다가 발견했다. `.dockerignore`에는 `venv/`만 있었는데, 이
      프로젝트가 실제로 쓰는 디렉터리명은 `.venv`(점 포함)라 전혀 매칭이
      안 되고 있었다 - `.gitignore`는 두 이름을 다 올바르게 제외하고
      있어서(git 쪽만) 아무도 눈치채지 못한 채 오래 방치된 것으로 보인다.
      직접 확인해보니 `.venv/`가 267MB, `.mypy_cache/`(이것도 제외 목록에
      아예 없었음)가 77MB로, `docker build`/`docker-compose build`를
      실행할 때마다 이 340MB+가 Docker 데몬으로 그대로 전송되고 있었다
      (다만 `Dockerfile`이 `COPY app ./app`처럼 필요한 것만 명시적으로
      복사하는 구조라 실제 이미지 안에 들어가진 않는다 - 빌드 시작 전
      컨텍스트 전송 단계의 낭비였다). `.dockerignore`를 `.gitignore`와
      맞춰 `.venv/`, `.mypy_cache/`, `.pytest_cache/`, `.coverage`,
      `htmlcov/`, `*.db` 등을 추가했다. 59/80/87번 라운드에서 정적 설정
      파일에 확립한 것과 같은 패턴으로 `tests/test_dockerignore.py`를
      추가해 핵심 항목(`.venv/`, `.mypy_cache/`, `.pytest_cache/`)이
      조용히 빠지는 회귀를 막는다 - 수정 전 파일로 되돌리면 이 테스트가
      실제로 실패하는 것도 확인했다. 이 샌드박스에는 Docker 데몬이 없어
      실제 `docker build`로 빌드 컨텍스트 크기 감소를 직접 재현하지는
      못했지만, 두 디렉터리의 실제 존재/용량(`du -sh`)과 이전 제외
      패턴이 그 이름과 전혀 일치하지 않았다는 점은 직접 확인했다. 설정
      파일만 바뀐 라운드라 Python 코드/모델 변경이 없어 문서 갱신이나
      마이그레이션은 해당 없다.

## 백로그 (67라운드)

- [x] 91. 직접 붙여넣어 만든 퀴즈의 RAG 원본 텍스트가 임베딩 API 일시
      장애 시 영영 복구 불가능하게 유실되던 문제, 그리고 같은 계열의
      면접연습 문답 재시도 누락 수정 - 이번 라운드는 서브에이전트에게
      독립적인 코드 조사를 맡겨 찾아낸 항목이다. `QuizService.
      create_quiz()`는 `study_session_id` 없이(=사용자가 직접 텍스트를
      붙여넣어) 만든 퀴즈만, 그 원본 텍스트를 커밋 후 별도로 `RagService.
      index_content()`로 색인했다 - 코드 주석에도 "다른 곳에는 색인되어
      있지 않다"고 명시돼 있을 만큼, 이 텍스트의 유일한 영구 저장 위치가
      바로 그 색인(knowledge_chunks 행)이었다. 그런데 `index_content()`는
      임베딩 호출이 실패하면(Ollama 일시 장애 등) 색인 없이 조용히
      반환하도록 설계돼 있다(RAG는 부가 기능이라 실패해도 본 기능을
      막으면 안 되므로) - 즉 퀴즈 생성 자체는 성공하지만 그 순간 하필
      임베딩이 실패하면, 원본 텍스트는 DB 어디에도 남지 않고 영영
      사라진다. 이 실패를 나중에 잡아줘야 할 안전망인 `rag_backfill_
      service.backfill_unindexed_content()`(42/61번에서 다룬 그 매일
      도는 재시도 job)는 `study_message`/`interview_review` 두
      source_type만 다뤄서 `quiz_source`는 애초에 재시도 대상에도 없었다
      - 재시도할 원본조차 없으니 재시도해도 소용없었을 것이다. 같은
      원인 계열로, 면접연습 문답(`interview_practice_turn`)도 답변
      제출 시점에 똑같이 동기 색인되는데 이 백필 job에서 빠져 있었다
      (다만 이건 답변/피드백 자체는 `interview_practice_turns` 테이블에
      영구 보존되므로 재시도용 원본은 있었다 - 안전망만 없었을 뿐).
      `quizzes` 테이블에 `source_text` 컬럼을 추가하는 마이그레이션을
      만들어 사용자가 직접 붙여넣은 텍스트를 이제 영구 보존하고
      (학습 세션에서 파생된 경우는 원본이 이미 study_message에 있으니
      중복 저장하지 않음), `backfill_unindexed_content()`에 `quiz_source`
      (source_text가 있고 아직 색인 없는 퀴즈)와 `interview_practice_turn`
      (답변이 있고 아직 색인 없는 턴) 두 그룹을 LEFT JOIN 패턴으로
      추가해 반환값을 2-튜플에서 4-튜플로 확장했다. 수동 전체 재색인
      스크립트(`scripts/backfill_knowledge_chunks.py`, 57번에서 다룸)도
      같은 두 source_type을 놓치고 있어서 함께 맞췄다. "생성 시점
      임베딩 실패" 상태를 그대로 재현하는(원본은 있고 색인만 없는)
      테스트를 두 source_type 모두에 추가해 백필이 정확히 그 행만
      찾아 복구하는지, 그리고 원본이 없거나(학습 세션 파생 퀴즈) 아직
      대상이 아닌(미답변 턴) 행은 건드리지 않는지 확인했다 - 수정 전
      코드로는 반환 튜플 크기부터 안 맞아 두 테스트가 즉시 실패하는
      것도 확인했다. 기존 `backfill_unindexed_content()` 호출부(테스트
      4곳, 실제 스케줄러 진입점)의 튜플 언패킹도 전부 4-튜플에 맞게
      갱신했다. `rag_backfill_service.py`는 새 테스트로 100% 커버리지를
      유지한다. API 응답 형태나 사용자 대상 동작은 그대로라(`source_text`
      는 어떤 응답 스키마에도 노출되지 않음) 문서 갱신은 필요 없었고,
      스키마 변경이 있어 마이그레이션을 만들고 upgrade → `alembic check`
      (드리프트 없음) → downgrade → 재upgrade → 재확인까지 전부 검증했다.

## 백로그 (68라운드)

- [x] 92. 퀴즈 답안 제출의 중복 방지 로직이 진짜 동시 요청 앞에서는
      뚫릴 수 있던 check-then-act 문제 수정 - 이번에도 서브에이전트에게
      독립 조사를 맡겼는데, 이번엔 이미 알려진 항목(RAG 백필 등)을
      피해서 다른 각도(동시성 등)를 보라고 구체적으로 지시했다.
      `QuizService.submit_answers()`는 `_find_recent_duplicate_attempt()`
      로 "최근 5초 안에 완전히 같은 답안 제출이 있었는지"를 확인한
      뒤에야 새 `QuizAttempt`를 커밋한다 - 네트워크 재시도나 이중
      클릭으로 완전히 같은 답안이 거의 동시에(별도 트랜잭션으로) 두
      번 오면, 53/78/83번에서 고친 것과 같은 계열의 경쟁으로 둘 다
      "최근 제출 없음"을 보고 통과해 `QuizAttempt`를 두 개 만들 수
      있었다 - 코드 주석이 스스로 명시한 "네트워크 재시도 시 중복
      방지"라는 목적을 정확히 그 상황에서 못 지키는 셈이다. 다만 이
      건 서브에이전트의 최초 보고("이 로직이 테스트 자체가 아예
      없다")를 그대로 믿지 않고 직접 `tests/test_quiz.py`를 검색해
      확인해보니 순차 재시도(진짜 동시 요청이 아닌) 케이스는 이미
      `test_resubmitting_identical_answers_quickly_returns_same_attempt`
      등으로 잘 테스트되어 있었다 - 비어있던 건 "진짜 동시" 케이스뿐이었다.
      53번(회원가입)이 DB unique 제약으로, 78번(면접연습)이 `WHERE
      answer IS NULL` CAS로 막은 것과 달리, 이 중복 판정은 "완전히
      같은 답안이 아주 최근에"라는 시간 창 조건이 있어 영구적인 unique
      제약으로는 표현할 수 없다(그러면 며칠 뒤 우연히 같은 답으로
      재도전하는 정상적인 케이스까지 막아버림) - 그래서 대신 `QuizRepository.
      get_for_user_locked()`(`SELECT ... FOR UPDATE`)로 같은 퀴즈+
      사용자의 제출 자체를 직렬화해, 먼저 도착한 요청이 커밋을 마칠
      때까지 나중 요청이 기다렸다가 그제야 (이미 커밋된) 직전 제출을
      보게 만들었다. 이 잠금은 Postgres(운영)에서만 실제로 걸린다 -
      SQLite(테스트/로컬)는 FOR UPDATE 자체를 지원하지 않아 조용히
      일반 SELECT로 컴파일된다는 걸 직접 컴파일해 확인했다. 그래서
      이 동시성 자체는 54번 때와 같은 이유로 SQLite 기반 테스트로
      재현할 수 없다 - 대신 리포지토리 메서드가 실제로 세션에 전달하는
      statement를 가로채, 그걸 Postgres 방언으로 다시 컴파일해 SQL에
      "FOR UPDATE"가 포함되는지 확인하는 테스트를 추가했다(`.with_for_
      update()`를 실수로 지우면 이 테스트가 잡아내는 것도 확인). 이
      한계를 솔직하게 로드맵에 남긴다 - 완벽한 검증은 아니지만, 최소
      한 의도한 메커니즘이 실제 코드에 들어있다는 것과 운영 DB에서
      효과가 있다는 것(SQL이 FOR UPDATE를 요청함)은 보장한다. `quiz_
      repository.py`는 새 테스트로 100% 커버리지를 유지한다. 응답
      형태/API 계약은 그대로라 문서 갱신은 필요 없었고, 모델/스키마
      변경도 아니라 마이그레이션은 필요 없었다.

## 백로그 (69라운드)

- [x] 93. 학습챗만 Ollama 호출 실패를 500으로 응답해 다른 AI 생성
      엔드포인트(퀴즈/면접연습/면접복기)와 상태 코드가 어긋나 있던
      문제 수정 - 이번에도 서브에이전트에게 독립 조사를 맡겼고, 이번엔
      "라우트 간 에러 응답 일관성" 각도로 구체적으로 지시했다.
      `QuizService`/`InterviewPracticeService`/`InterviewReviewService`
      는 전부 `OllamaServiceError`(Ollama 엔진 호출 실패)를 502(우리
      서버가 아니라 업스트림 AI 엔진의 문제)로 응답하도록 모듈
      전역 `_GENERATION_FAILED = HTTPException(502, "...생성에
      실패했습니다. 다시 시도해주세요.")` 상수를 두고 있었는데,
      `StudyService`만 `send_message`/`stream_message` 두 곳 모두
      500(우리 서버 자체의 예상 못 한 오류)으로 응답했다 - 완전히
      같은 실패 원인(Ollama 엔진 다운/타임아웃 등)인데 어느 기능에서
      겪었느냐에 따라 다른 상태 코드가 나가는 셈이었다. 상태 코드로
      "502/503이면 재시도 유도, 500이면 버그 신고 유도" 같은 분기를
      하는 프론트라면, 학습챗의 AI 엔진 장애를 엉뚱하게 "우리 서버
      버그"로 잘못 분류하게 된다. `study_service.py`에도 같은
      `_GENERATION_FAILED` 패턴(502 + 통일된 한글 메시지)을 추가하고
      두 호출부 모두 이걸 쓰도록 바꿨다. 기존 테스트(`test_user_
      message_preserved_when_ai_call_fails`)가 정확히 500을 기대하고
      있어서 이 라운드 전에는 이 불일치가 테스트로 고정돼 있었다는
      뜻이었다 - 502로 갱신했다. `study_service.py`는 새/기존 테스트로
      100% 커버리지를 유지한다. 응답 상태 코드가 바뀌는 사용자 대상
      동작 변화라(500→502) `FRONTEND_INTEGRATION.md`의 학습챗 섹션에
      다른 AI 생성 엔드포인트와 같은 502 안내를 추가했다. 모델/스키마
      변경은 아니라 마이그레이션은 필요 없었다.
