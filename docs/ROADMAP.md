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

## 백로그 (70라운드)

- [x] 94. 학습챗/퀴즈/면접연습/면접복기 목록 페이지네이션이 정렬
      기준 값이 같은 행 사이에서 항목을 중복으로 보여주거나 아예
      빠뜨릴 수 있던 문제 수정 - 배포 설정을 훑다가 발견했던 이전
      두 라운드와 달리, 이번엔 직접 모든 리포지토리의 `order_by`를
      쭉 훑어보다가 찾았다. `StudySessionRepository`/`QuizRepository`/
      `InterviewPracticeSessionRepository`/`InterviewReviewRepository`
      의 페이지네이션용 `list_for_user()`가 전부 단일 컬럼
      (`updated_at`/`created_at`/`interview_date`)만으로 `ORDER BY`
      했다 - 그 값이 같은 행이 여러 개면 그 사이의 순서는 SQL
      표준상 전혀 정의돼 있지 않다. `LIMIT`/`OFFSET`으로 나눠 받는
      페이지네이션은 "매번 같은 순서로 정렬된다"는 전제에 의존하는데,
      그 전제가 깨지면 같은 행이 두 페이지에 다시 나오거나(중복)
      어느 페이지에도 안 나올(누락) 수 있다. 특히 `InterviewReview.
      interview_date`는 하루 단위 정밀도의 사용자 입력값이라 - 하루에
      면접을 여러 번 본 경우처럼 - 동률이 실제로 흔하게 발생할 수
      있어 네 개 중 가장 심각했다(나머지 셋은 마이크로초 정밀도
      타임스탬프라 동률 확률은 훨씬 낮지만, 같은 논리적 결함을
      똑같이 안고 있었다). 네 메서드 모두 `id`를 2차 정렬 기준으로
      추가해 동률을 항상 같은 순서로 결정론적으로 깨지도록 했다.
      흥미롭게도 `interview_review`에는 이미 정확히 이 동률 상황을
      만드는 기존 테스트(`test_list_reviews_pagination`, 헬퍼가 모든
      복기에 같은 `interview_date`를 쓰고 있어서)가 있었는데도
      SQLite가 이 단순한 비동시성 시나리오에서 우연히 안정적인 순서를
      돌려줘서 계속 통과하고 있었다 - 직접 재현 스크립트로 확인함.
      즉 이 문제는 68번 라운드의 `SELECT ... FOR UPDATE`와 같은
      성격의 한계로, SQLite 기반 테스트로는 실제로 재현할 수 없다 -
      대신 각 리포지토리가 세션에 전달하는 실제 statement를 가로채,
      컴파일된 SQL의 `ORDER BY` 절에 기존 정렬 컬럼뿐 아니라 `id`도
      2차 기준으로 포함돼 있는지 확인하는 테스트를 4개(파일당 하나)
      추가했다 - 수정 전 코드로 되돌리면 이 테스트들이 실제로 실패
      하는 것도 확인했다. 응답 형태나 기본 정렬 기준(최신순)은
      그대로라 사용자 대상 문서 갱신은 필요 없었고, 모델/스키마
      변경도 아니라 마이그레이션은 필요 없었다.

## 백로그 (71라운드)

- [x] 95. 하루 한 번 도는 스케줄러 job들이 실행 시각이 아주 조금만
      밀려도 그날 실행을 통째로 조용히 건너뛸 수 있던 문제 수정 -
      이번에도 서브에이전트에게 독립 조사를 맡겼고, APScheduler 설정
      쪽을 구체적으로 보라고 지시했다. `app/core/scheduler.py`의
      `AsyncIOScheduler`는 FastAPI/uvicorn과 같은 이벤트 루프를
      공유하는데, `add_job()` 호출 세 곳 모두 `misfire_grace_time`을
      지정하지 않아 라이브러리 기본값인 1초가 적용되고 있었다 -
      실제 설치된 `apscheduler==3.11.3` 소스(`schedulers/base.py`의
      `_configure`, `executors/base.py`의 `run_job`)까지 직접 추적해
      확인했다. 예정된 실행 시각(예: 새벽 3시 정각)에 이벤트 루프가
      요청 처리/GC 등으로 1초 이상만 밀려도(평범한 트래픽에서 충분히
      있을 수 있는 일) 그 job은 재시도 없이 그날 실행을 통째로
      건너뛰고, `apscheduler.scheduler` 로거에 WARNING 한 줄만 남기고
      지나간다 - 이 앱은 `EVENT_JOB_MISSED`/`EVENT_JOB_ERROR` 리스너가
      전혀 없고 Sentry 같은 별도 에러 트래킹도 없어서, 그 로그 한
      줄을 누가 직접 보지 않는 한 놓친 사실 자체를 알 방법이 없었다.
      특히 `keep_supabase_alive`는 코드 주석에도 "7일 연속 정지를
      막는 게 목적"이라고 명시돼 있는데, 정작 이 job을 놓치기 쉽게
      만드는 좁은 기본 grace window와 아무 경보 장치가 없는 조합이
      그 목적 자체를 무력화할 수 있는 상태였다. 세 `add_job()` 호출
      모두 `misfire_grace_time=None`(실행 시각이 아무리 늦어도 다음
      트리거 전까지는 건너뛰지 않고 실행)으로 바꾸고, `EVENT_JOB_
      MISSED`/`EVENT_JOB_ERROR` 리스너를 추가해 이 앱 자신의 로거
      ("haruhan")에도 ERROR 레벨로 남기도록 했다(다른 곳의 `logger.
      exception(...)` 패턴과 동일한 가시성 수준). `tests/test_
      scheduler.py`를 새로 만들어 (1) 리스너가 MISSED/ERROR 이벤트를
      실제로 ERROR 레벨 로그로 남기는지, (2) 세 job 모두 `misfire_
      grace_time=None`으로 등록되는지 확인했다 - 수정 전 코드로는
      리스너 함수 자체가 없어 테스트 임포트부터 실패하는 것도
      확인했다. `scheduler.py`는 새 테스트로 100% 커버리지를
      유지한다. 사용자 대상 API 변경은 전혀 없는 내부 운영 안정성
      개선이라 문서 갱신은 필요 없었고, 모델/스키마 변경도 아니라
      마이그레이션은 필요 없었다.

## 백로그 (72라운드)

- [x] 96. 학습 세션 기반 퀴즈 생성에 소스 텍스트 길이 제한이 전혀
      적용되지 않고 있던 문제 수정 - 이번에도 서브에이전트에게 독립
      조사를 맡겼다. `core/config.py`의 `max_quiz_source_length`
      주석에는 "학습 세션 전체를 소스로 쓸 수 있어 일반 프롬프트
      제한보다 넉넉하게 둔다"고 명시돼 있어, 이 설정이 정확히
      `study_session_id`로 퀴즈를 만드는 경로를 감당하려고 만들어진
      값이라는 게 코드 스스로의 의도였다. 그런데 실제 적용은
      `QuizCreateRequest`의 Pydantic 검증기(`schemas/quiz.py`)뿐이고,
      이 검증기는 사용자가 `source_text`를 직접 붙여넣은 경우에만
      걸린다 - `study_session_id`와 `source_text`는 동시에 못 쓰게
      막혀 있어서, `QuizService.create_quiz()`가 그 세션의 메시지
      전부를 이어붙여 만드는 `source_text`는 이 검증을 원천적으로
      거칠 수가 없었다. `StudyMessageRepository.list_for_session()`
      은 세션의 메시지를 개수 제한 없이 전부 가져오므로, 학습챗
      세션이 계속 길어질수록(메시지 하나하나는 `max_prompt_length`
      로 제한되지만 개수 자체엔 제한이 없음) 이 문자열이 무한정
      커져서 Ollama 호출이 느려지거나 타임아웃되어 애꿎게 502로
      나가거나, 모델의 컨텍스트 윈도우를 넘겨 조용히 품질이 떨어질
      수 있었다 - 코드 자신이 "이 경로를 감당하려고 만든 값"이라고
      밝힌 설정이 정작 그 경로에서 한 번도 적용되지 않는 자기모순
      이었다. 직접 붙여넣기와 달리 사용자가 세션 길이를 조절할
      방법이 없으므로, 60번 라운드(학습챗 대화 히스토리 제한)와
      같은 접근으로 거부 대신 잘라내기를 택했다 - 길이를 넘으면
      가장 최근 대화만 남기고 앞부분을 버리되, 메시지 중간이 아니라
      줄바꿈 경계에서 잘리도록 보정했다. 이를 위해 `QuizService`가
      `settings: Settings`를 생성자로 주입받도록 바꾸고(다른 서비스와
      같은 패턴), 라우트의 `get_quiz_service` 의존성과 기존
      `QuizService(...)`를 직접 생성하는 테스트 3곳(`test_quiz.py`,
      `test_quiz_rag_indexing.py`, `test_quiz_submission_dedup.py`)
      모두 갱신했다. `MAX_QUIZ_SOURCE_LENGTH`를 아주 작게 줄이고
      세션에 메시지를 여러 개 쌓은 뒤, Ollama에 실제로 전달되는
      프롬프트를 가로채 가장 오래된 메시지는 안 남고 가장 최근
      메시지만 남는지 확인하는 테스트를 추가했다 - 단순히 생성자
      시그니처만 맞추고 잘라내기 로직 자체를 빼면 이 테스트가 실제로
      실패하는 것까지 확인해서(생성자 변경 자체가 아니라 잘라내기
      동작을 검증하는 테스트임을 재확인), 수정 전 코드로 되돌린
      뒤 다시 적용했다. `quiz_service.py`는 새 테스트로 100%
      커버리지를 유지한다. 아주 긴 세션으로 만든 퀴즈가 세션 초반
      내용을 반영 못 할 수 있다는 사용자 대상 동작 변화라
      `FRONTEND_INTEGRATION.md`의 퀴즈 생성 섹션에 안내를 추가했다.
      모델/스키마 변경은 아니라 마이그레이션은 필요 없었다.

## 백로그 (73라운드)

- [x] 97. 데이터 export(`GET /export/me`)가 직접 붙여넣어 만든 퀴즈의
      원본 텍스트(`Quiz.source_text`)를 누락하고 있던 문제 수정 -
      이번에도 서브에이전트에게 독립 조사를 맡겼다. `db/models/quiz.py`의
      `source_text` 컬럼 주석은 "이 텍스트는 study_message/
      interview_review와 달리 다른 어떤 테이블에도 저장되지 않는다"고
      스스로 밝히고 있다 - 즉 직접 붙여넣기로 만든 퀴즈에서는 이
      컬럼이 사용자가 원래 입력한 내용이 DB에 남는 유일한 자리다.
      그런데 `schemas/export.py`의 `QuizExport`에는 `source_text`
      필드 자체가 없었고, `export_service.py`의 `_build_quizzes()`도
      이 컬럼을 전혀 읽지 않았다 - 학습챗의 `StudyMessageExport.content`,
      면접복기의 `InterviewReviewExport.content`는 원본을 그대로
      내보내면서, 퀴즈만 사용자 본인 데이터를 통째로 되돌려주지
      못하는 export 완전성 구멍이었다. 72번 라운드 로드맵 항목이
      "source_text는 어떤 응답 스키마에도 노출되지 않는다"고 적어둔
      것과 겹쳐 보일 수 있지만, 그건 퀴즈 조회 API(`QuizResponse`/
      `QuizDetailResponse`)에서 사용자가 이미 갖고 있는 입력을 그대로
      돌려줄 필요가 없다는 의도적 설계였고, export는 "본인 데이터를
      빠짐없이 내려받는다"는 전혀 다른 목적이라 이 구멍은 별개의
      누락이다. `QuizExport`에 `source_text: str | None` 필드를
      추가하고 `_build_quizzes()`가 `quiz.source_text`를 채우도록
      고쳤다. 기존 `test_export.py`의
      `test_export_my_data_groups_each_entitys_children_correctly`는
      이미 `source_text: "소스 1"`/`"소스 2"`로 퀴즈를 만들고
      있었는데도 export 응답에서 이 값을 확인하는 assert가 없어서
      이 구멍을 잡아내지 못하고 있었다 - 여기에 assert를 추가하고,
      직접 붙여넣은 퀴즈는 `source_text`가 그대로 나오고 학습 세션
      기반 퀴즈는(원본이 이미 `study_sessions` 쪽 메시지로 export에
      들어가 있으므로 중복 없이) `null`로 남는지 함께 확인하는 테스트
      (`test_export_includes_pasted_quiz_source_text_but_not_for_session_based_quiz`)
      를 추가했다. `export.py`/`export_service.py` 모두 새 테스트로
      100% 커버리지를 유지한다(전체 333개 테스트 통과, 전체 커버리지
      99%, mypy 클린). DB 컬럼은 이미 존재하던 것을 스키마/서비스
      계층에서 읽어 노출하기만 한 변경이라 마이그레이션은 필요
      없었다. export 응답 스키마가 바뀌는 사용자 대상 변화라
      `FRONTEND_INTEGRATION.md`의 export 섹션 예시 응답에
      `source_text` 필드를 추가하고, 직접 붙여넣은 퀴즈에서만
      채워지고 세션 기반 퀴즈는 `null`이라는 설명을 덧붙였다.

## 백로그 (74라운드)

- [x] 98. 학습챗 세션을 삭제해도 그 세션의 메시지들이 RAG로 색인해둔
      내용은 지워지지 않아, 사용자가 지운 대화가 이후 무관한 학습챗
      질문의 그라운딩 자료로 계속 되살아나던 문제 수정 - 이번에도
      서브에이전트에게 독립 조사를 맡겼다. `StudyService.send_message`/
      `stream_message`는 메시지마다 `rag.index_content(source_type=
      "study_message", source_id=message.id, ...)`로 개별 색인해두는데,
      `StudyService.delete_session`은 그냥 `sessions.delete(study_session)`
      후 커밋만 하고 끝났다. `KnowledgeChunk.source_id`는 의도적으로
      FK가 아닌 폴리모픽 참조(`db/models/knowledge_chunk.py`)라서,
      `study_sessions -> study_messages`의 CASCADE는 메시지 로우까지만
      지우고 `knowledge_chunks`는 전혀 건드리지 못한다. `RagService.
      retrieve_relevant()`는 source가 실제로 남아있는지 확인하는 절차
      없이 사용자의 전체 색인을 코사인 유사도로만 훑어 그라운딩에
      쓰므로, 삭제된 세션의 내용이 계속 다른 학습챗 답변에 참고자료로
      섞여 들어갈 수 있었다 - 사용자 입장에서는 "지운 대화 내용이
      AI 답변에서 다시 튀어나오는" 눈에 띄는 사생활/정합성 문제다.
      같은 "세션 삭제 전 자식 id를 먼저 모아 개별 forget_content" 패턴을
      이미 쓰고 있는 `InterviewPracticeService.delete_session`을 그대로
      따라 했다 - `delete_session`이 (CASCADE로 사라지기 전에)
      `messages = await self._messages.list_for_session(session_id)`로
      메시지 id를 먼저 모아두고, 세션 삭제/커밋 후 각 메시지에 대해
      `rag.forget_content(source_type="study_message", source_id=
      message.id)`를 호출하도록 고쳤다. 기존 `test_study.py::
      test_delete_session`은 세션이 정말 지워지는지만 확인할 뿐
      `knowledge_chunks`는 전혀 보지 않아 이 구멍을 잡아내지 못했고,
      `test_account_deletion_cascade.py`가 `knowledge_chunks` 청소를
      검증하긴 하지만 그건 계정 전체 삭제(별개의 `user_id` CASCADE
      경로) 케이스라 "계정은 유지한 채 세션 하나만 삭제" 경로는
      아무 테스트도 없었다. 새 테스트 파일
      `test_study_session_delete_rag_cleanup.py`를 추가해, 메시지를
      보내 색인이 2개(사용자/어시스턴트) 생기는 것까지 확인한 뒤
      세션을 지우고 그 사용자의 색인이 0개가 되는지 검증했다 - 수정
      전 코드로 되돌려서 이 테스트가 실제로 실패하는 것까지 확인한
      뒤(`git stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다.
      `study_service.py`는 새 테스트로 100% 커버리지를 유지한다(전체
      334개 테스트 통과, 전체 커버리지 99%, mypy 클린). 순수 서비스
      계층 내부 정리 로직이고 API 응답 형태는 그대로라 모델/스키마
      변경이나 마이그레이션, `FRONTEND_INTEGRATION.md` 갱신은 필요
      없었다.

## 백로그 (75라운드)

- [x] 99. 데이터 export(`GET /export/me`)에만 레이트리밋이 전혀 걸려있지
      않던 문제 수정 - 이번에도 서브에이전트에게 독립 조사를 맡겼다.
      로그인/회원가입/토큰 refresh 등 브루트포스 우려가 있는 엔드포인트는
      `auth_rate_limit`(분당 5회), 학습챗/퀴즈/면접연습/면접복기의 LLM
      호출 경로는 `chat_rate_limit`(분당 10회)으로 전부 보호돼 있는데,
      `export.py`의 `export_my_data`만 `@limiter.limit(...)` 데코레이터가
      아예 없었다. `ExportService.export_user_data()`는 이 앱에서 유일하게
      페이지네이션 없이 학습챗 세션/메시지/퀴즈/문항/시도/답안/면접연습
      세션/턴/면접복기를 전부 한 번에 긁어오는 엔드포인트라(86번 라운드에서
      N+1은 이미 고쳤지만 쿼리 수 자체가 줄어든 것뿐, 결과 크기 자체엔
      제한이 없음), 반복 호출을 막을 방법이 없으면 계정 이력이 쌓일수록
      호출 한 번의 DB 부하도 함께 커지는데 이를 제한할 수단이 전혀
      없었다 - 다른 모든 비용이 큰/쓰기 경로는 신경 써서 막아놓고 정작
      "내 데이터 전체를 한 번에 덤프하는" 가장 무거운 읽기 경로 하나만
      빠뜨린 비일관성이었다. `auth_rate_limit`/`chat_rate_limit`은 각각
      브루트포스, LLM 비용이라는 성격이 뚜렷해 재사용하기보다, "계정 이력
      크기에 비례하는 무제한 DB 부하"라는 별개의 이유로 `export_rate_limit`
      (기본 분당 10회)을 새로 추가하고 `export_my_data`에 적용했다. 92번
      라운드의 `test_submit_quiz_is_rate_limited`와 같은 패턴으로
      `EXPORT_RATE_LIMIT=2/minute`로 낮춰 세 번째 호출이 `429`로 거부되는지
      확인하는 테스트(`test_export_my_data_is_rate_limited`)를 추가했고,
      데코레이터를 빼면 이 테스트가 실제로 실패하는 것까지 확인한 뒤
      (`git stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다. 전체
      335개 테스트 통과, 전체 커버리지 99%, mypy 클린. 모델/스키마
      변경이 아니라 마이그레이션은 필요 없었다. 레이트리밋이 걸리는
      엔드포인트 목록과 export 섹션에 안내를 추가하도록
      `FRONTEND_INTEGRATION.md`를 갱신했다.

## 백로그 (76라운드)

- [x] 100. 학습챗/면접복기 스트리밍 WebSocket이 깨진 JSON 프레임을 받으면
      처리되지 않은 예외로 연결이 비정상 종료되던 문제 수정 - 이번에도
      서브에이전트에게 독립 조사를 맡겼다. `study.py`의 `stream_message`와
      `interview_review.py`의 `stream_create_review`는 둘 다
      `await asyncio.wait_for(websocket.receive_json(), ...)`를 부르면서
      `asyncio.TimeoutError`만 잡고 있었는데, Starlette의
      `WebSocket.receive_json()`은 내부적으로 `json.loads(text)`를 그대로
      호출할 뿐 예외를 전혀 잡지 않는다 - 즉 클라이언트가 깨진/부분
      전송된 JSON을 보내면(느린 모바일 네트워크, 클라이언트 버그 등)
      `json.JSONDecodeError`가 그대로 터진다. WebSocket 스코프에는 HTTP용
      전역 예외 핸들러(`main.py`의 `ServerErrorMiddleware`)가 적용되지
      않으므로(스코프가 `"http"`가 아니면 그냥 통과시킴), 이 예외는 어디서도
      잡히지 않고 그대로 ASGI 서버까지 올라가 연결이 처리되지 않은 서버
      예외로 끊긴다 - 같은 라우트 안에서 빈 내용/길이 초과/레이트리밋
      초과 등 다른 모든 잘못된 입력은 `{"type": "error", "detail": "..."}`
      프레임으로 우아하게 처리하고 연결을 유지하는 것과 정면으로 모순되는
      동작이었다. `study.py`는 한 가지 문제가 더 있었는데, JSON이긴 하지만
      객체가 아닌 페이로드(`[1,2,3]`, `42`, `null` 등)가 오면
      `payload.get("content")`에서 `AttributeError`가 나서 이 역시 같은
      방식으로 죽었다(`interview_review.py`는 `InterviewReviewCreateRequest.
      model_validate(raw_payload)`가 non-dict 입력에도 `ValidationError`를
      던지도록 pydantic이 이미 처리해줘서 이 두 번째 문제는 없었다 - 직접
      실행해 확인). 두 라우트 모두 `except json.JSONDecodeError`를 추가해
      에러 프레임을 보내고 루프를 계속하도록 고쳤고, `study.py`에는
      `isinstance(payload, dict)` 가드도 추가했다. 기존 WS 테스트는 전부
      `ws.send_json({...})`으로 항상 올바른 형태의 페이로드만 보내고
      있어서 이 구멍을 전혀 잡아내지 못했다 - `ws.send_text("...")`로
      깨진 텍스트 프레임을 보내는 테스트
      (`test_stream_message_rejects_malformed_json_frame`,
      `test_stream_create_review_rejects_malformed_json_frame`)를 각각
      추가하고, 에러 프레임을 받은 뒤에도 연결이 살아있어 두 번째
      메시지에 응답하는지까지 확인했다. 수정 전 코드로 되돌려서 두
      테스트 모두 실제로 `JSONDecodeError`로 실패하는 것을 직접 확인한
      뒤(`git stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다. 전체
      337개 테스트 통과, 전체 커버리지 99%, mypy 클린. 순수 라우트 계층
      예외 처리 수정이라 모델/스키마 변경이나 마이그레이션은 필요
      없었다. `FRONTEND_INTEGRATION.md`는 이미 "실패하면 에러 프레임이
      오고 연결은 끊기지 않는다"고 문서화해뒀던 기존 계약을 실제 동작이
      이제야 지키게 된 것뿐이라 별도 갱신은 필요 없었다.

## 백로그 (77라운드)

- [x] 101. 면접복기 수정(`PATCH /interview-reviews/{id}`)이 content를 바꿀 때
      RAG 재색인이 원자적이지 않아, 거의 동시에 두 번 수정하면
      `knowledge_chunks`에 중복 행(하나는 최신 content와 안 맞는 낡은 내용)이
      남을 수 있던 문제 수정 - 이번에도 서브에이전트에게 독립 조사를 맡겼다.
      `RagService.index_content()`는 `delete_for_source()`로 기존 색인을
      지운 뒤, Ollama 임베딩 호출(네트워크 왕복)을 거쳐서야 `create()`로 새
      청크를 만든다 - 이 둘 사이에 커밋이 없고, `KnowledgeChunk.source_id`는
      의도적으로 FK가 아닌 폴리모픽 참조라 `(source_type, source_id)`에
      유니크 제약도 없다(`db/models/knowledge_chunk.py`). `update_review()`는
      이 메서드를 호출하기 전 `get_for_user()`로 잠금 없이 리뷰를 읽는
      check-then-act였다 - 이중 클릭이나 느린 네트워크에서의 클라이언트
      재시도로 서로 다른 content를 담은 두 PATCH 요청이 거의 동시에 오면,
      둘 다 "content가 바뀌었다"고 판단해 각자 피드백을 생성/커밋하고
      각자 `index_content()`를 부르는데, 첫 번째 요청의 삭제-임베딩 대기
      구간에 두 번째 요청의 삭제-임베딩-생성이 끼어들면 최종적으로 같은
      `source_id`에 대해 청크가 두 개 남을 수 있다(하나는 실제
      `interview_reviews.content`와 더 이상 일치하지 않는 내용). 다른
      모든 `index_content()` 호출부(퀴즈/학습챗/면접연습)는 생성 시점에
      한 번만 색인하고 수정 후 재색인하는 경로가 없어서, 이 패턴은
      `update_review()`가 유일했다(직접 각 서비스의 호출부를 다 확인함).
      92번 라운드에서 퀴즈 답안 제출 중복 방지에 쓴 것과 같은 패턴으로,
      `InterviewReviewRepository`에 `get_for_user_locked()`(`SELECT ...
      FOR UPDATE`)를 추가해 같은 복기에 대한 수정을 직렬화하고,
      `rag.index_content()` 호출을 `session.commit()` 이전으로 옮겨 삭제
      -임베딩-생성 전 구간이 잠금이 걸린 트랜잭션 안에서 끝나도록 고쳤다 -
      먼저 도착한 요청의 커밋(재색인까지 포함)이 끝나야 잠금이 풀리고,
      나중 요청은 그제야 이미 반영된 content를 보고 다시 판단한다. 92번
      라운드와 같은 이유로 SQLite는 `FOR UPDATE`를 조용히 빼고 컴파일하므로
      이 잠금에 의존하는 동시성 자체는 SQLite 기반 테스트로 재현/검증할 수
      없다 - 대신 세션에 전달되는 실제 statement를 가로채 Postgres 방언으로
      다시 컴파일해 `FOR UPDATE`가 포함되는지 확인하는 테스트
      (`test_get_for_user_locked_requests_row_lock_on_postgres`)를
      추가했고, `get_for_user_locked` 자체가 없던 수정 전 코드에서 이
      테스트가 실제로 `AttributeError`로 실패하는 것까지 확인한 뒤(`git
      stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다. 전체 338개
      테스트 통과, 전체 커버리지 99%, mypy 클린. 순수 서비스/리포지토리
      계층 변경(잠금 쿼리 추가 + 호출 순서 재배치)이라 모델/스키마 변경이나
      마이그레이션, `FRONTEND_INTEGRATION.md` 갱신은 필요 없었다.

## 백로그 (78라운드)

- [x] 102. 면접연습에서 "답변 제출"과 "면접 종료"를 거의 동시에 누르면
      이미 종료된 세션에 아무도 답할 수 없는 턴이 하나 남을 수 있던 문제
      수정 - 이번에도 서브에이전트에게 독립 조사를 맡겼다.
      `InterviewPracticeService.submit_answer()`와 `.complete_session()`은
      둘 다 `practice_session.status != "in_progress"`인지 확인한 뒤(check)
      느린 Ollama 호출을 거쳐서야 쓰는(act) check-then-act였는데,
      `InterviewPracticeSessionRepository`에는 92번(퀴즈)/101번(면접복기)
      라운드에서 같은 종류의 버그를 막으려고 추가한 `get_for_user_locked()`가
      없었다 - 세션 상태를 잠그지 않고 읽는 유일한 곳이었다. 마지막 질문에
      대한 "답변 제출"(`POST .../answers`)과 "면접 종료"(`POST .../complete`)
      요청이 거의 동시에(이중 클릭, 느린 네트워크에서의 재시도) 오면 둘 다
      "아직 진행중"이라고 읽고 통과할 수 있다 - `complete_session`이 먼저
      커밋해 세션을 `completed`로 만들어도, 이미 시작된 `submit_answer`는
      상태를 다시 확인하지 않고 뒤늦게 `mark_answered_if_pending`으로 자기
      턴을 응답 완료 처리하고 새 다음 턴까지 만들어버린다 - `submit_answer`는
      호출마다 상태를 `in_progress`로 재확인하므로, 이렇게 남은 다음 턴은
      이미 끝난 세션에 영원히 답할 수 없는 채로 남는다(완결된 면접
      연습에는 미답변 턴이 없어야 한다는 도메인 불변조건이 깨짐). 92/101번
      라운드와 같은 패턴으로 `get_for_user_locked()`(`SELECT ... FOR
      UPDATE`)를 추가해 `submit_answer`/`complete_session` 둘 다 이걸로
      세션을 읽도록 바꿔, 같은 세션에 대한 두 작업이 직렬화되게 했다.
      기존 테스트는 `mark_answered_if_pending`이 자기 자신과 경합하는
      경우(같은 질문에 답변 중복 제출)만 다뤘을 뿐 `submit_answer`와
      `complete_session`이 서로 경합하는 경우는 전혀 다루지 않았다.
      92/101번 라운드와 같은 이유로 SQLite는 `FOR UPDATE`를 조용히 빼고
      컴파일하므로 이 잠금에 의존하는 동시성 자체는 SQLite 기반 테스트로
      재현/검증할 수 없다 - 대신 세션에 전달되는 실제 statement를 가로채
      Postgres 방언으로 다시 컴파일해 `FOR UPDATE`가 포함되는지 확인하는
      테스트(`test_get_for_user_locked_requests_row_lock_on_postgres`)를
      추가했고, `get_for_user_locked` 자체가 없던 수정 전 코드에서 이
      테스트가 실제로 `AttributeError`로 실패하는 것까지 확인한 뒤(`git
      stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다. 전체 339개
      테스트 통과, 전체 커버리지 99%, mypy 클린. 순수 서비스/리포지토리
      계층 변경이라 모델/스키마 변경이나 마이그레이션,
      `FRONTEND_INTEGRATION.md` 갱신은 필요 없었다.

## 백로그 (79라운드)

- [x] 103. 102번 라운드 자체가 만든 회귀 두 가지를 수정 - 이번에도 서브에이전트
      에게 독립 조사를 맡겼는데, "다른 각도를 찾아라"가 아니라 "직전 라운드가
      실제로 의도대로 동작하는지 재검증하라"는 관점에서 102번 라운드의
      `get_for_user_locked()` 도입 자체가 만든 회귀를 찾아냈다.

      **(1) 잠금이 `submit_answer()`를 자기 자신과도 직렬화시켜, 이중 클릭/
      네트워크 재시도가 엉뚱한 다음 턴에 답을 붙여버릴 수 있던 문제.**
      102번 라운드 전에는 `current_turn`을 위치(`turns[-1]`)로 고른 뒤
      `mark_answered_if_pending(current_turn.id, ...)`의 CAS(`WHERE answer IS
      NULL`)가 "같은 턴에 대한 중복 제출"을 턴 id 기준으로 정확히 걸러줬다.
      102번 라운드가 추가한 `get_for_user_locked()`는 `submit_answer()`
      맨 앞에서 세션 행을 잠그는데, Postgres에서는 이 잠금이 먼저 온
      요청의 커밋이 끝날 때까지 나중 요청을 그 자리에서 재운다 - 나중
      요청이 깨어나 그제서야 처음(=유일한) 턴 조회를 하면, 이미 먼저 온
      요청이 답변 완료 처리하고 새로 만들어둔 "다음" 턴을 자기가 답할
      차례라고 잘못 고르게 된다(그 턴 자체는 진짜로 미답변 상태라 CAS도
      막지 못함) - 사용자가 첫 질문에 낸 답이 엉뚱하게 두 번째 질문에
      붙어버리고, RAG에도 그 뒤섞인 질문-답 쌍이 영구히 색인되는 데이터
      정합성 문제였다. 잠금 전에 "지금 답하려는 턴"을 먼저 확정해두고
      (`expected_turn_id`), 잠금을 얻은 뒤 다시 읽은 턴이 여전히 그 턴과
      일치하는지 확인해서, 그 사이 상황이 바뀌었으면 엉뚱한 턴에 적용하는
      대신 안전하게 409로 거부하도록 고쳤다.

      **(2) 그 수정 자체가 다시 만든, 세션 status 재확인이 무력화되는
      문제.** (1)의 수정으로 `submit_answer()`가 세션을 두 번 읽게
      됐는데(잠금 전 한 번, 잠금 후 한 번), SQLAlchemy는 기본적으로 세션의
      identity map에 이미 로드된 객체를 같은 PK로 다시 조회해도 속성을
      새로 덮어쓰지 않는다 - 그래서 `populate_existing=True` 없이는, 잠금
      후 다시 읽은 `practice_session.status`가 실제로는 (그 사이
      `complete_session()`이 커밋했을) 최신 값이 아니라 잠금 전 조회 때
      캐시해둔 옛날 값 그대로였다. 이러면 잠금 자체(FOR UPDATE로 대기)는
      정상 동작해도 102번 라운드가 막으려던 "완료된 세션에 뒤늦게 턴이
      추가되는" 원래 버그가 그대로 재발할 수 있었다 - `get_for_user_locked()`
      의 조회에 `.execution_options(populate_existing=True)`를 추가해,
      항상 방금 커밋된 실제 값으로 객체를 갱신하도록 강제했다. `QuizRepository`/
      `InterviewReviewRepository`의 `get_for_user_locked()`(92/101번
      라운드)는 같은 메서드 안에서 잠금 전에 같은 행을 먼저 읽는 코드가
      없어 이 문제가 없다는 것도 직접 확인했다.

      (1)은 서로 다른 세션 두 개(같은 커넥션을 쓰되 순차적으로만 동작해
      SQLite 단일 커넥션 제약을 안 건드림)로 진짜 격리된 상태를 만들어
      재현했다 - 하나의 세션을 공유해서 재현하면 `mark_answered_if_pending`
      의 세션 단위 bulk update 동기화가 우연히 다른 이유로 거부해버려
      진짜 버그를 못 잡는다는 것도 직접 확인하고 버렸다. 처음엔 경쟁을
      `list_for_session()` 호출 지점에 주입했다가, 그 타이밍이 실제
      Postgres의 블로킹 지점(`get_for_user_locked()` 자체)과 달라 구버전
      코드도 우연히 통과해버리는 걸 발견해 `get_for_user_locked()` 호출
      지점으로 다시 옮겼다 - 이렇게 옮긴 뒤에야 수정 전 코드에서 테스트가
      실제로 실패(예외 없이 조용히 성공)하는 것을 확인했다. (2)도 같은
      두-세션 기법으로 "완료된 세션"과 "삭제된 세션" 두 경우 모두 재현하는
      테스트를 추가했고, `.execution_options(populate_existing=True)`를
      빼면 "완료된 세션" 테스트가 실제로 실패하는 것까지 확인한 뒤 복원했다.
      전체 342개 테스트 통과, 전체 커버리지 99%, mypy 클린(`interview_
      practice_service.py`/`interview_practice_repository.py` 모두 100%
      유지). 순수 서비스/리포지토리 계층 로직 수정이라 모델/스키마 변경이나
      마이그레이션, `FRONTEND_INTEGRATION.md` 갱신은 필요 없었다.

## 백로그 (80라운드)

- [x] 104. 103번 라운드가 고친 identity map 낡은 값 문제의 형제 사례를
      마저 고침 - 이번 라운드는 "새 각도를 찾아라"가 아니라 "직전 라운드가
      스스로 발견한 버그 계열이 다른 곳에도 있는지 회의적으로 재검증하라"는
      관점으로 서브에이전트에게 맡겼다. `submit_answer()`는 잠금
      (`get_for_user_locked`) 전후로 `list_for_session()`도 두 번 부르는데,
      103번 라운드는 세션 객체 쪽(`get_for_user_locked`)에만
      `populate_existing=True`를 추가했을 뿐 턴 목록 쪽
      (`InterviewPracticeTurnRepository.list_for_session`)은 그대로 뒀다.
      다음 턴을 새로 만드는 분기(질문이 더 남은 경우)는 새 턴 자체가
      이 세션에서 처음 로드되는 행이라 문제가 없지만, **마지막 질문**
      (다음 턴을 만들지 않는 분기)에서는 잠금 대기 중 다른 요청이 이미
      답해버린 바로 그 턴을, 잠금 후 재조회에서도 첫 조회 때 로드해둔
      낡은 객체를 그대로 돌려받아 여전히 "미답변"으로 잘못 본다 - 103번
      라운드가 추가한 재확인(`current_turn.id != expected_turn_id or
      current_turn.answer is not None`)이 이 분기에서만 무력화되어, 값싸게
      걸러냈어야 할 걸 못 걸러내고 실제 AI 호출까지 낭비한 뒤에야
      `mark_answered_if_pending`의 CAS(원시 UPDATE라 이 캐싱 문제와 무관)
      가 뒤늦게 409로 막는다 - 데이터가 잘못 저장되진 않지만(CAS가 최종
      방어선으로 여전히 동작), 103번 라운드가 재확인을 추가한 원래 목적
      (비싼 재작업 없이 안전하게 거부하기)이 이 한 분기에서만 깨져 있었다.
      직접 스크립트로 재현해 확인했다: 수정 전에는 이 시나리오에서 가짜
      Ollama의 `chat()`이 두 번(먼저 온 요청 몫 + 뒤늦은 요청이 낭비한 몫)
      호출됐다. `list_for_session()`에도 같은 `.execution_options
      (populate_existing=True)`를 추가해 고쳤다 - 다른 세 호출부는 메서드당
      한 번만 불러 이 위험이 없지만, `get_for_user_locked()`와 같은 방어를
      리포지토리 메서드 자체에 걸어두는 게 더 안전하다고 판단했다.
      `MAX_INTERVIEW_QUESTIONS=1`로 첫 답변이 곧바로 마지막 답변이 되게
      만들고, 103번 라운드와 같은 두-세션 잠금 주입 기법으로 "다른 요청"이
      먼저 답하게 한 뒤, 바깥쪽 제출이 (여전히 409로 거부되긴 하지만)
      `chat()`을 다시 호출하지 않는지 확인하는 테스트를 추가했다 - 수정
      전 코드로 되돌려서 `chat_calls == 2`로 실제 실패하는 것까지 확인한
      뒤(`git stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다. 서브
      에이전트는 이 김에 `QuizRepository`/`InterviewReviewRepository`의
      `get_for_user_locked()`(92/101번 라운드)도 재검증했는데, 두 서비스
      모두 잠금 조회 전에 같은 행을 먼저 읽는 코드가 없어 이 문제가 없다는
      103번 라운드의 판단을 다시 확인했고, `user_service.py`의 게스트
      업그레이드 lost-update 경쟁(79번 라운드가 낮은 우선순위로 남겨둔
      건)도 다시 봤지만 새로운 근거는 없어 그대로 남겨뒀다. 전체 343개
      테스트 통과, 전체 커버리지 99%, mypy 클린(`interview_practice_
      repository.py` 100% 유지). 순수 리포지토리 계층 읽기 동작 수정이라
      모델/스키마 변경이나 마이그레이션, `FRONTEND_INTEGRATION.md` 갱신은
      필요 없었다.

## 백로그 (81라운드)

- [x] 105. 학습챗 메시지 전송 중 세션이 삭제되면 처리되지 않은
      `IntegrityError`(500)로 끝나던 문제 수정 - 78~80번 라운드가 연속으로
      면접연습 한 파일만 파고든 걸 감안해, 이번엔 서브에이전트에게 완전히
      다른 영역을 보라고 명시적으로 지시했다. `send_message()`/
      `stream_message()`는 둘 다 세션 존재를 확인한 뒤 느린 Ollama 호출을
      거쳐서야 `assistant_message`를 만드는 check-then-act다 - `StudyMessage.
      session_id`는 `nullable=False`, `ondelete="CASCADE"` FK라서, 그 사이
      다른 탭/요청이 `DELETE /study/sessions/{id}`로 이 세션을 지워버리면
      (CASCADE로 방금 만든 user_message도 함께 사라짐) `session_id`가 더는
      존재하지 않는 부모를 가리키게 되어 `assistant_message` INSERT가
      `IntegrityError`로 실패한다. 이걸 잡는 코드가 어디에도 없어서, 애써
      받은 AI 응답을 저장도 못 하고 버리면서 REST 경로는 처리되지 않은
      예외로 500이 나가고, WebSocket 경로는(100번 라운드에서 이미 확인한
      대로 WS 스코프에는 전역 예외 핸들러가 적용되지 않아) 연결 자체가
      처리되지 않은 서버 예외로 죽어버렸다. 이 사이 다른 세션과 관련된
      check-then-act 경쟁들(92/101/102/103/104번 라운드)은 전부 `SELECT
      ... FOR UPDATE` 잠금으로 고쳤지만, 이번엔 다르게 접근했다 - 학습챗
      스트리밍은 응답 생성 시간이 잠금을 걸어두기엔 너무 길 수 있고, FK
      위반은 SQLite에서도 실제로 재현되는 진짜 제약 위반(잠금 흉내가
      필요 없음)이라, `auth_service.py`/`user_service.py`가 이미 이메일
      중복 가입 경쟁에 쓰고 있던 `except IntegrityError: rollback() + 409
      (여기서는 404)로 변환` 패턴을 그대로 재사용하는 게 더 간단하고
      확실했다. `send_message()`/`stream_message()` 둘 다 `assistant_message`
      생성 부분을 이 패턴으로 감쌌다 - `_SESSION_NOT_FOUND`(이미 있는 404)를
      그대로 재사용해, WS 라우트의 기존 `except HTTPException` 처리(100번
      라운드가 확립)가 자동으로 `{"type": "error"}` 프레임으로 바꿔준다.
      가짜 Ollama가 응답을 반환하기 "직전"에 별도 세션으로 세션을 완전히
      지우도록 만들어 REST/WS 두 경로 모두 결정론적으로 재현하는 테스트
      (`tests/test_study_message_session_deleted_race.py`)를 추가했고, 수정
      전 코드에서 `IntegrityError`가 그대로 새어나오는 것까지 확인한 뒤
      (`git stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다. 서브에이전트는
      같은 패턴(체크 후 느린 AI 호출 후 그 세션을 참조하는 자식 행 생성)이
      `QuizService.create_quiz()`(학습 세션 기반 퀴즈 생성)에도 있다고
      짚어줬는데 - `source_study_session_id`는 `ondelete="SET NULL"`이라
      CASCADE로 지워지진 않지만 INSERT 시점에 이미 없어진 부모를 참조하면
      마찬가지로 `IntegrityError`가 날 수 있다 - 이번 라운드 범위에는
      포함하지 않고 다음 라운드를 위해 여기 남겨둔다. 전체 345개 테스트
      통과, 전체 커버리지 99%, mypy 클린(`study_service.py` 100% 유지).
      순수 서비스 계층 예외 처리 추가라 모델/스키마 변경이나 마이그레이션은
      필요 없었고, 이미 문서화된 404(`Study session not found`) 케이스로
      수렴하는 수정이라 `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (82라운드)

- [x] 106. 학습 세션 기반 퀴즈 생성 중 그 세션이 삭제되면 처리되지 않은
      `IntegrityError`(500)로 끝나던 문제 수정 - 81번 라운드가 같은 버그
      계열의 형제 사례로 직접 짚어둔 것을 이번 라운드에서 마저 고쳤다.
      `QuizService.create_quiz()`는 `study_session_id`로 만드는 경로에서
      학습 세션 존재를 확인한 뒤(`get_for_user`), 느린 Ollama 호출(파싱
      실패 시 최대 2회 재시도)을 거쳐서야 `Quiz`를 만드는 check-then-act다 -
      `Quiz.source_study_session_id`는 `ondelete="SET NULL"`이라 CASCADE로
      지워지진 않지만, 그 사이 다른 요청이 이 학습 세션을 지워버리면 이
      INSERT 시점엔 이미 사라진 부모를 참조하게 되어 여전히 `IntegrityError`
      가 난다(SET NULL은 기존 행이 삭제될 때의 동작이지, 존재하지 않는
      부모를 가리키는 새 INSERT를 허용해주지 않는다). 81번 라운드에서
      `study_service.py`의 `send_message`/`stream_message`에 적용한 것과
      똑같은 패턴 - `auth_service.py`/`user_service.py`가 이메일 중복 가입
      경쟁에 쓰던 `except IntegrityError: rollback() + 에러 응답 변환`을
      재사용해, 기존 `_SESSION_NOT_FOUND`(404)로 변환했다. `Quiz` 생성 +
      문항 생성 + 커밋을 한 `try` 블록으로 묶었다(`QuizRepository.create()`
      가 즉시 flush해 이 시점에 위반이 드러남). 가짜 Ollama가 퀴즈 JSON을
      반환하기 "직전"에 별도 세션으로 학습 세션을 완전히 지우도록 만들어
      이 타이밍을 결정적으로 재현하는 테스트
      (`tests/test_quiz_session_deleted_race.py`)를 추가했고, 수정 전
      코드에서 `IntegrityError`가 그대로 새어나오는 것까지 확인한 뒤(`git
      stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다. 전체 346개
      테스트 통과, 전체 커버리지 99%, mypy 클린(`quiz_service.py` 100%
      유지). 순수 서비스 계층 예외 처리 추가라 모델/스키마 변경이나
      마이그레이션은 필요 없었고, 이미 문서화된 404 케이스로 수렴하는
      수정이라 `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (83라운드)

- [x] 107. 비밀번호를 변경해도 기존에 발급된 refresh token이 전혀 폐기되지
      않던 문제 수정 - 이번엔 78~82번 라운드가 연달아 파던 "check-then-act
      경쟁"/"identity map 낡은 값" 두 버그 계열을 다시 찾지 말고 완전히
      다른 영역을 보라고 서브에이전트에게 명시적으로 지시했다.
      비밀번호 변경(`PATCH /users/me`)은 보통 "계정이 뚫린 것 같다"는
      의심에서 나오는 행동인데, `UserService.update_profile()`은 비밀번호
      해시만 바꾸고 커밋할 뿐 이 사용자의 refresh token은 전혀 건드리지
      않았다 - 공격자가 refresh token을 훔친 상태라면(XSS, 로그 유출,
      방치된 기기 등), 피해자가 비밀번호를 바꿔도 그 refresh token은
      `refresh_token_expire_days`(기본 14일)까지 여전히 유효해서 공격자는
      `POST /auth/refresh`로 계속 로그인 상태를 유지할 수 있다 - 비밀번호
      변경이라는 보안 조치의 의미가 사실상 없어지는 셈이다. `docs/
      FRONTEND_INTEGRATION.md`도 원래 "비밀번호를 변경한 다른 기기 전부
      로그아웃시키기"를 프론트가 `PATCH /users/me` 이후 별도로 `DELETE
      /auth/sessions`를 호출하는 2단계 워크플로로 문서화해뒀을 뿐, 서버가
      이걸 보장하진 않았다 - 그 2단계를 프론트가 실제로 구현하지 않으면
      (문서화된 단일 목적 엔드포인트인 `PATCH /users/me`만 호출하는 클라이언트
      라면 특히) 공격자 세션을 포함한 다른 모든 세션이 그대로 살아있게 된다.
      `auth_service.py`가 refresh token 재사용 탐지/전체 로그아웃에 이미
      쓰고 있는 `RefreshTokenRepository.revoke_all_for_user()`를
      `UserService`에도 주입해, 비밀번호가 바뀔 때 같은 커밋 안에서 이
      계정의 모든 refresh token을 함께 폐기하도록 고쳤다 - `PATCH /users/me`
      로 인증하는 access token만으로는 어느 refresh token이 지금 요청을
      보낸 클라이언트 것인지 구분할 수 없어(`FRONTEND_INTEGRATION.md`가
      이미 밝혀둔 사실), `DELETE /auth/sessions` 전체 로그아웃과 동일하게
      요청을 보낸 클라이언트 자신의 세션도 함께 끊긴다(비밀번호 변경 직후
      다시 로그인해야 함 - 널리 받아들여지는 보안 관행). `email`만 바꾸는
      경우는 세션을 건드리지 않는다 - 공격자가 이미 살아있는 세션으로
      직접 저지를 수 있는 행동에 이메일 자체는 추가 방어선이 되지 않고,
      비밀번호 케이스만큼 뚜렷한 근거가 없어 범위를 좁게 유지했다. 서명
      가입 → 비밀번호 변경 → 변경 전 refresh_token으로 `POST /auth/refresh`
      시도가 `401`로 거부되는지 확인하는 테스트
      (`test_update_password_revokes_existing_refresh_tokens`)를 추가했고,
      수정 전 코드에서 이 refresh 호출이 그대로 `200`을 반환하는 것까지
      확인한 뒤(`git stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다.
      전체 347개 테스트 통과, 전체 커버리지 99%, mypy 클린(`user_service.py`
      100% 유지). 기존 `revoke_all_for_user()`/스키마를 그대로 재사용해
      모델 변경이나 마이그레이션은 필요 없었다. 비밀번호 변경 시 클라이언트
      자신도 재로그인해야 하는 사용자 대상 동작 변화라
      `FRONTEND_INTEGRATION.md`의 1-6/1-8 섹션에 안내를 추가했다.

## 백로그 (84라운드)

- [x] 108. `DEFAULT_QUIZ_QUESTION_COUNT`가 `MAX_QUIZ_QUESTION_COUNT`보다
      커져도 아무 검증 없이 배포될 수 있어, `question_count`를 생략한
      (아마 대다수인) 퀴즈 생성 요청이 조용히 그 한도를 넘는 문항 수를
      요청할 수 있던 문제 수정 - 78~83번 라운드가 파던 두 버그 계열
      (check-then-act 경쟁, identity map 낡은 값)과 무관한 새 영역을 보라고
      서브에이전트에게 지시했다. `QuizCreateRequest._validate_source_and_count`
      (`schemas/quiz.py`)는 `question_count`를 클라이언트가 직접 보낸
      경우에만 `max_quiz_question_count`와 비교해서 거부하고, 생략된
      경우는 `default_quiz_question_count`를 그냥 채워 넣을 뿐 그 값이
      max를 넘는지는 전혀 확인하지 않는다 - 그리고 `Settings`에는 이 두
      설정값 사이의 관계를 검증하는 코드가 없었다. 운영자가 비용 절감을
      위해 `MAX_QUIZ_QUESTION_COUNT`만 낮추거나(예: 20 -> 10), "더 풍성한
      기본값"을 위해 `DEFAULT_QUIZ_QUESTION_COUNT`만 올리면, `question_count`
      를 생략한 요청은 검증 에러 하나 없이 그 한도를 넘는 문항 수의 퀴즈를
      계속 생성하게 되어 방금 낮춘 한도가 사실상 무의미해진다. `LOG_LEVEL`/
      `ENVIRONMENT`(73/74번 라운드)처럼 "설정 오류는 요청 시점이 아니라
      시작 시점에 막는다"는 이 코드베이스의 기존 방침을 그대로 따라,
      `Settings`에 `model_validator(mode="after")`로 `default_quiz_
      question_count <= max_quiz_question_count`를 검증하는 교차 필드
      검증을 추가했다(기존 세 검증은 전부 단일 필드용 `field_validator`라
      이번이 첫 교차 필드 검증이다). 이 검증을 추가하자 기존 테스트
      (`test_create_quiz_rejects_question_count_over_max`)가 `MAX_QUIZ_
      QUESTION_COUNT=3`만 설정하고 `DEFAULT`는 그대로 둬(=5) 이제는 유효하지
      않은 조합이 되어 `Settings()` 생성 자체가 실패하는 걸 발견해, 그
      테스트에 `DEFAULT_QUIZ_QUESTION_COUNT=3`도 함께 설정하도록 고쳤다 -
      이 테스트가 우연히 우리가 막으려는 바로 그 모순된 조합을 이미
      전제하고 있었다는 뜻이기도 하다. `test_config.py`에 값이 같을 때
      통과하는 경우와 초과할 때 거부되는 경우를 각각 확인하는 테스트를
      추가했고, 수정 전 코드에서 후자가 실제로 통과(=버그가 재현됨)하는
      것까지 확인한 뒤(`git stash`로 수정 부분만 되돌렸다가 복원) 다시
      적용했다. `.env.example`은 이미 5/20으로 유효한 조합이라 갱신할
      필요가 없었다. 전체 349개 테스트 통과, 전체 커버리지 99%, mypy
      클린(`config.py` 100% 유지). 순수 설정 계층 검증 추가라 모델/스키마
      변경이나 마이그레이션은 필요 없었고, 클라이언트가 보내는 요청/응답
      형태는 그대로라 `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (85라운드)

- [x] 109. `CHAT_RATE_LIMIT`/`AUTH_RATE_LIMIT`/`EXPORT_RATE_LIMIT` 문자열이
      잘못돼도 시작 시점엔 전혀 검증되지 않아, HTTP 경로는 레이트리밋이
      조용히 꺼지고 WebSocket 경로는 첫 메시지마다 서버가 죽던 문제 수정 -
      108번 라운드가 `Settings`에 처음으로 교차 필드 검증을 추가한 걸
      계기로, 서브에이전트에게 "다른 설정 필드 쌍에도 이런 무검증 구멍이
      있는지" 보게 했더니 이 세 문자열 필드 자체가 아예 무검증이라는 걸
      찾아냈다. 이 값들은 `limiter.limit(lambda: get_settings().xxx_rate_
      limit)`(HTTP, slowapi 데코레이터)과 `check_rate_limit()`(WebSocket,
      `core/rate_limit.py`) 두 경로에서 각각 요청마다 파싱되는데, 잘못된
      값 하나가 두 경로에서 서로 다른, 둘 다 나쁜 방식으로 실패한다는 걸
      직접 확인했다: (1) HTTP 쪽(slowapi 내부)은 파싱 실패를 `except
      ValueError`로 잡아 로그만 남기고 그 요청의 레이트리밋을 조용히
      건너뛰어(fail-open) 로그인/회원가입 브루트포스 방어나 export DoS
      방어(99번 라운드)가 티도 안 나게 꺼져버린다 - (2) `check_rate_limit()`
      은 `item = parse(rate_limit)` 호출에 예외 처리가 전혀 없어서, 학습챗/
      면접복기 스트리밍이 첫 메시지를 보내자마자 처리되지 않은 `ValueError`
      로 죽어버린다(100번 라운드에서 이미 확인한 대로 WebSocket 스코프에는
      전역 예외 핸들러가 적용되지 않음 - 깨진 JSON 프레임 문제와 같은
      성격의 취약점이 여기서도 재현됨). `"10/min"`처럼 사람이 자연스럽게
      쓰기 쉬운 축약형이나 빈 문자열이 실제로 두 경로 모두를 이렇게
      실패시킨다는 걸 `limits` 라이브러리로 직접 재현해 확인했다.
      `LOG_LEVEL`/`ENVIRONMENT`/108번 라운드와 같은 "설정 오류는 요청
      시점이 아니라 시작 시점에 막는다"는 방침에 따라, 세 필드에 공유
      `field_validator`를 추가해 slowapi가 내부적으로 쓰는 것과 같은
      파서(`limits.util.parse_many`)로 미리 검증하도록 고쳤다. 이 파서를
      애플리케이션 코드에서 직접 import하게 되면서, 지금까지 `slowapi`의
      전이 의존성으로만 설치돼 있던 `limits`를 `requirements.txt`에 직접
      명시(`limits==5.8.0`, 현재 설치된 버전과 일치)하도록 추가했다 - 이제
      직접 import하는 패키지를 slowapi의 전이 의존성 변경에 따라 조용히
      끌려다니게 두지 않기 위함이다. 값이 올바를 때 통과하는 경우와
      (`"10/min"`, 빈 문자열, `"10"`, `"bogus-rate-limit"`) 각각 거부되는
      경우를 세 필드 전부에 대해 확인하는 테스트를 추가했고, 수정 전
      코드에서 12개 케이스 전부가 실제로 통과(=버그가 재현됨)하는 것까지
      확인한 뒤(`git stash`로 수정 부분만 되돌렸다가 복원) 다시 적용했다.
      전체 364개 테스트 통과, 전체 커버리지 99%, mypy 클린(`config.py`
      100% 유지). 순수 설정 계층 검증 추가라 모델/스키마 변경이나
      마이그레이션은 필요 없었고, 클라이언트가 보내는 요청/응답 형태는
      그대로라 `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (86라운드)

- [x] 110. `DEFAULT_QUIZ_QUESTION_COUNT`에 아래쪽 한계가 없어, 0이나 음수로
      설정되면 `question_count`를 생략한 모든 퀴즈 생성 요청이 항상
      502로 실패하던 문제 수정 - 85번 라운드 조사에서 후순위 후보로
      남겨뒀던 걸 이번 라운드에서 마저 처리했다. 요청 스키마 쪽
      `QuizCreateRequest.question_count`는 `Field(ge=1)`로 이미 하한이
      걸려 있지만, `question_count`를 생략했을 때 그 자리를 그대로
      채우는 `default_quiz_question_count`는 108번 라운드가 추가한
      `max_quiz_question_count`와의 상한 비교만 거칠 뿐 하한은 전혀
      검증하지 않았다. `DEFAULT_QUIZ_QUESTION_COUNT=0`(또는 음수)이
      설정되면(상한 검증은 통과함 - 0 ≤ max) `question_count`를 생략한
      모든 퀴즈 생성 요청이 "0문항을 만들어달라"는 프롬프트를 매번
      내보내고, `_GeneratedQuiz.questions`가 `min_length=1`이라 항상
      검증에 실패해 재시도(`_MAX_QUIZ_GENERATION_ATTEMPTS`)까지 Ollama
      호출을 낭비한 뒤 502로 끝난다 - `question_count`를 생략하는
      경로(아마 대다수) 전체가 이 설정 하나로 영구히 고장 나는 셈이었다.
      새 검증을 따로 만들지 않고, 108번 라운드에서 추가한
      `_validate_quiz_question_count_defaults` 안에 `default_quiz_
      question_count >= 1` 검증을 함께 넣었다(같은 필드를 다루는 관련
      검증이라 이 필드 하나에 여러 `model_validator`를 만들기보다 묶어
      두는 게 자연스럽다고 판단). `Settings`의 다른 필드들처럼 `Field(ge=1)`
      대신 검증기로 처리해 이 파일의 기존 관례(모든 제약이 `field_validator`
      /`model_validator`를 통해 걸림, `Field(...)`는 한 번도 안 씀)를
      그대로 따랐다. `0`과 `-1` 둘 다 거부되는지 확인하는 테스트를
      추가했고, 수정 전 코드에서 둘 다 실제로 통과(=버그가 재현됨)하는
      것까지 확인한 뒤(`git stash`로 수정 부분만 되돌렸다가 복원) 다시
      적용했다. 전체 366개 테스트 통과, 전체 커버리지 99%, mypy 클린
      (`config.py` 100% 유지). 순수 설정 계층 검증 추가라 모델/스키마
      변경이나 마이그레이션은 필요 없었고, 클라이언트가 보내는 요청/응답
      형태는 그대로라 `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (87라운드)

- [x] 111. 대용량 payload를 막으려고 만든 `MaxBodySizeMiddleware`가, 숫자가
      아닌 `Content-Length` 헤더 하나로 오히려 모든 요청을 처리되지 않은
      예외(500)로 죽일 수 있던 문제 수정 - 84~86번 라운드가 연달아
      `Settings` 검증만 팠던 걸 감안해, 이번엔 서브에이전트에게 완전히
      다른 영역을 보라고 지시했다. `core/middleware.py`의
      `MaxBodySizeMiddleware.__call__`은 `int(content_length)`를 예외
      처리 없이 그대로 호출하는데, 이 미들웨어는 FastAPI 라우팅/예외
      핸들러보다 바깥(ASGI 계층)에 등록돼 있어서(`app.add_middleware`로
      전체를 감싸는 가장 바깥쪽) 앱의 `HTTPException`/`RequestValidationError`
      핸들러를 아예 거치지 못하고, `ValueError`가 곧바로 `main.py`의 전역
      `Exception` 핸들러까지 올라가 `500 {"code": "internal_error"}`로
      끝난다. `Content-Length: abc`처럼 숫자가 아니거나 빈 헤더 하나만
      보내면(스캐너, 프록시, 단순 오타 등으로 실제로 흔히 생김) *어떤
      라우트든* 이 500을 유발할 수 있었다 - 대용량 payload로부터 방어하려는
      미들웨어 자신이 사소한 malformed 헤더 하나에 모든 요청을 죽이는
      더 큰 문제를 만드는 셈이었고, 클라이언트 잘못인데도 상태 코드는
      "서버 버그"로 잘못 분류되며 에러 로그에도 "처리되지 않은 예외"로
      잘못 잡혔다. 이 미들웨어 자신의 docstring이 이미 "Content-Length가
      없는 chunked 요청까지는 못 막는다"고 인정하고 있어서, 파싱 실패도
      같은 취급(크기를 알 수 없는 것으로 보고 통과시킴)으로 처리하도록
      고쳤다 - 이 미들웨어의 목적(대용량 차단)과 무관한 요청을 새로
      거부하는 대신, 이미 문서화된 한계를 하나 더 추가하는 선에서
      범위를 좁게 유지했다. `Content-Length: abc`를 보내는 요청이 500
      대신 정상 처리되는지 확인하는 테스트를 추가했고, 수정 전 코드에서
      실제로 `ValueError: invalid literal for int()...`가 그대로 새어나와
      500이 되는 것까지 확인한 뒤(`git stash`로 수정 부분만 되돌렸다가
      복원) 다시 적용했다. 전체 367개 테스트 통과, 전체 커버리지 99%,
      mypy 클린(`middleware.py` 100% 유지). 순수 미들웨어 계층 파싱 방어
      추가라 모델/스키마 변경이나 마이그레이션은 필요 없었고, 정상
      요청의 동작은 그대로라 `FRONTEND_INTEGRATION.md` 갱신도 필요
      없었다.

## 백로그 (88라운드)

- [x] 112. 비밀번호 검증(`verify_password`)에 72바이트 길이 가드가 없어,
      너무 긴 비밀번호로 로그인하거나 프로필 수정/계정 삭제를 시도하면
      처리되지 않은 예외(500)가 나던 문제 수정 - 87번 라운드까지 이미 판
      `Settings`/미들웨어 대신, 이번엔 서브에이전트에게 repositories,
      `models.py` 캐싱, `ollama_service.py` 타임아웃, CORS 설정을 먼저
      훑어 깨끗함을 확인시킨 뒤 `core/password.py`를 보게 했다.
      `hash_password()`는 72바이트를 넘는 입력을 `PasswordTooLongError`로
      명시적으로 거부하지만(bcrypt가 72바이트를 넘으면 조용히 잘라버리는
      걸 막기 위함), 정작 기존 비밀번호와 "대조"하는 `verify_password()`에는
      같은 가드가 없었다. `bcrypt.checkpw()`는 72바이트를 넘는 입력에
      대해 자르는 대신 `ValueError`를 던지는데, 이게 그대로 라우트까지
      새어나가 500이 됐다. 실제로 두 경로에서 재현 가능했다:
      (1) `POST /auth/login` - `LoginRequest.password`의
      `max_length=72`(`app/schemas/auth.py`)는 "문자 수" 기준이라, 멀티바이트
      문자(예: 한글 72자)를 쓰면 스키마 검증은 통과하고도 UTF-8 바이트
      수는 72를 넘을 수 있음. (2) `PATCH /users/me`, `DELETE /users/me`의
      `current_password` 필드(`app/schemas/user.py`의
      `UserUpdateRequest`/`AccountDeletionRequest`)는 애초에 길이 제한이
      전혀 없어 임의로 긴 문자열을 그대로 보낼 수 있음. 실제 앱을 통해
      재현했다 - 임시 테스트 파일(`client` fixture 사용, `get_db`가 올바르게
      오버라이드된 상태)로 `DELETE /users/me`에 긴 `current_password`를
      보내 `app/api/v1/routes/users.py` → `user_service.py:110` →
      `password.py:38`까지 이어지는 전체 트레이스백에서 처리되지 않은
      `ValueError`를 확인한 뒤 임시 파일은 삭제했다. 72바이트를 넘는
      입력은 어차피 실제로 저장된 비밀번호와 일치할 수 없으므로(그런
      긴 비밀번호는 애초에 해시로 저장될 수 없었다), `verify_password()`
      맨 앞에서 바이트 길이를 확인해 넘으면 예외 대신 곧바로 `False`를
      반환하도록 고쳤다 - 더미 해시 비교 분기보다 먼저 조기 반환하지만,
      이 조기 반환은 제출된 비밀번호의 길이(공격자가 이미 아는 값)에만
      의존하고 `hashed_password`/계정 존재 여부와는 무관하므로, 기존의
      타이밍 기반 계정 존재 여부 유출 방어(존재하지 않는 사용자도 항상
      더미 해시와 bcrypt 비교를 수행)와는 겹치지 않는다. 스키마 쪽
      `current_password`에 `max_length=72`를 추가하는 방안도 검토했지만,
      서비스 계층의 이 수정만으로 이미 크래시가 완전히 막히고 동작도
      "불일치로 처리"로 일관되므로, 별도 스키마 제약을 추가하는 건
      불필요한 범위 확장이라 판단해 하지 않았다.
      `tests/test_password.py`에 `test_verify_password_rejects_password_over_byte_limit`
      (`"가" * 72`로 실제 해시와 대조 - 문자 수는 72지만 바이트 수는 넘음)와
      `test_verify_password_rejects_password_over_byte_limit_with_none_hash`
      (더미 해시 비교 경로에서도 같은 가드 적용 확인)를 추가했다. `git
      stash`로 `password.py` 수정만 되돌린 뒤 두 테스트가 정확히 같은
      `ValueError: password cannot be longer than 72 bytes...`로 실패하는
      것까지 확인하고 나서 수정을 복원했다. 전체 369개 테스트 통과,
      전체 커버리지 99%(`password.py` 100% 유지), mypy 클린. 순수
      서비스 계층 로직 수정이라 모델/스키마 변경이나 마이그레이션은
      필요 없었고, 클라이언트 입장에서 기존에도 "틀린 비밀번호"였어야
      할 케이스가 500 대신 정상적인 401/403으로 바뀌는 것뿐이라
      `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (89라운드)

- [x] 113. 퀴즈 문항의 `correct_answer` 컬럼만 `String(500)`이라, AI가 500자를
      넘는 정답을 생성하면 Postgres INSERT 자체가 실패해 처리되지 않은
      500이 되던 문제 수정 - 서브에이전트에게 rate_limit/cache/health/
      scheduler/security/tokens/metrics/dependencies, export/rag 서비스
      로직, models/chat/metrics/health 라우트 등 이번 세션에서 아직 안 본
      영역과 "스키마 검증이 실제 DB 컬럼 제약과 안 맞는 곳"을 함께 보라고
      지시했다. `app/db/models/quiz_question.py`를 보면 `question_text`/
      `explanation`은 `Text`(무제한), `choices`는 `JSON`(무제한)인데
      `correct_answer`만 `String(500)`으로 남아 있었고, `quiz_service.py`의
      `_GeneratedQuiz`/`_generate_quiz`는 `correct_answer`가 `choices` 중
      하나인지만 검증할 뿐 길이는 전혀 보지 않는다. 정답 문자열이
      우연히(예: 서술형에 가까운 보기, 비영어권 긴 표현 등) 500자를 넘으면
      `self._questions.create(...)` → `session.commit()`에서 INSERT가
      실패한다 - `create_quiz`는 이미 세션 삭제 레이스를 위해
      `except IntegrityError`를 두고 있지만(81/106번 라운드), 로컬 Postgres
      클러스터를 직접 띄워 재현해보니 이 길이 초과는 asyncpg 방언이
      `IntegrityError`가 아니라 더 일반적인 `sqlalchemy.exc.DBAPIError`
      (`orig`는 `asyncpg.exceptions.StringDataRightTruncationError`)로
      올라와 그 `except`에 전혀 걸리지 않고 그대로 새어나가는 것까지
      확인했다(실제 사용자/퀴즈/문항 행을 만들어 501자 정답으로 INSERT해
      정확히 이 예외를 관찰함). `correct_answer`는 결국 `choices` 중
      하나와 완전히 같아야 하는 값이라 임의로 자르면 채점 로직 자체가
      깨지므로, 잘라내거나 별도로 예외 처리를 추가하는 대신 형제
      컬럼들과 마찬가지로 길이 제한 없는 `Text`로 컬럼 타입 자체를
      맞췄다(alembic 마이그레이션 `089b9a2d134f` 추가, 로컬 Postgres에서
      upgrade/downgrade/재upgrade 왕복과 실제 501자 INSERT 성공까지
      확인). 회귀 테스트는 두 가지를 추가했다:
      `test_quiz_question_correct_answer_column_has_no_length_limit`은
      모델의 `correct_answer` 컬럼 타입에 길이 제한이 없는지(`.length is
      None`) 직접 확인하는 테스트로, `git stash`로 모델 수정만 되돌리면
      정확히 `500 is not None`으로 실패하는 것을 확인했다 - SQLite는
      `String(500)`이어도 길이를 강제하지 않아, 이 테스트만이 백엔드와
      무관하게 이 회귀를 실제로 잡아낸다는 점을 테스트 docstring에 그대로
      남겼다. `test_create_quiz_persists_correct_answer_over_500_chars`는
      600자 정답으로 퀴즈 생성부터 제출/채점까지 전체 흐름이 값 손실
      없이 통과하는지 확인하는 통합 테스트이지만, SQLite에서는 수정 전
      코드로도 통과해버리므로(길이 미강제) 그 사실이 이 테스트가 실제로
      잡아내는 회귀는 아님을 정직하게 문서화했다 - 실제 크래시/수정 확인은
      위에서 설명한 로컬 Postgres 재현으로 별도 검증했다. 전체 371개
      테스트 통과, 전체 커버리지 99%(`quiz_question.py` 100% 유지), mypy
      클린. `correct_answer` 컬럼 타입 변경이라 alembic 마이그레이션이
      필요했고(위 확인 완료), API 응답 스키마(`app/schemas/quiz.py`)는
      애초에 `correct_answer: str`로 길이 제약이 없어 변경이 필요 없었으며
      클라이언트 관점에서 동작 변화가 없어 `FRONTEND_INTEGRATION.md`
      갱신도 필요 없었다.

## 백로그 (90라운드)

- [x] 114. RAG 검색(`retrieve_relevant`)이 학습챗 메시지/면접연습 턴마다
      사용자의 색인된 기록 "전체"를 이벤트 루프에서 그대로 채점해, 기록이
      쌓일수록 그 워커의 다른 모든 동시 요청까지 함께 멈추던 문제 수정 -
      89번 라운드가 남긴 두 후보(모델 목록 API 인증/레이트리밋 누락,
      코사인 유사도 차원 불일치)보다, 서브에이전트가 스스로 새로 찾은
      이 항목이 실제로 도달 가능하고 서비스가 잘 쓰일수록 더 나빠진다는
      점에서 우선순위가 높다고 판단해 이걸 골랐다. `knowledge_chunk_
      repository.py`의 `list_for_user()`는 `LIMIT`/`ORDER BY` 없이 사용자의
      색인된 청크(학습챗 메시지, 퀴즈 소스, 면접복기 등 - 만료/정리 로직이
      없어 계속 쌓이기만 함) 전부를 가져오고, `rag_service.py`의
      `retrieve_relevant()`는 그 전체에 대해 `_cosine_similarity`를 순수
      파이썬 루프(`await` 없음)로 돌린 뒤 정렬해 상위 K개를 뽑았다.
      이 계산은 CPU 바운드라 파이썬 GIL 아래에서 이벤트 루프를 그대로
      점유하므로, 색인된 기록이 수천 건으로 늘어난 사용자가 메시지 하나를
      보낼 때마다 그 시간만큼 같은 워커에서 처리 중이던 다른 모든 사용자의
      요청까지 함께 멈춘다 - 서비스가 오래/많이 쓰일수록(제품이 성공할수록)
      더 심해지는, 이번 세션에서 다룬 다른 이슈들과 달리 시간이 지날수록
      저절로 나빠지는 유형의 문제다. `knowledge_chunk.py`의 기존 주석도
      "청크가 수천 개 넘어가면 pgvector 전환 고려"라고 이미 이 한계를
      인지하고 있었다 - 다만 그 전환 없이도 "채점 자체를 이벤트 루프
      밖으로 빼는" 훨씬 가벼운 수정으로 검색 결과(정확도/순위)는 그대로
      유지하면서 "다른 사용자를 막는" 부분만 없앨 수 있어 이 범위로
      한정했다. ORM 세션 객체를 스레드에서 직접 만지면 위험하므로, 이미
      로드된 `(embedding, content)` 순수 데이터만 추출해
      `asyncio.to_thread`로 스레드 풀에 위임하는 `_rank_top_k()` 헬퍼를
      새로 만들었다. 회귀 테스트
      (`test_retrieve_relevant_scores_candidates_off_the_event_loop_thread`)는
      시간차 기반 측정 대신(asyncio.sleep은 실제 경과 시간 기준이라 이벤트
      루프가 막혀 있어도 타이머가 이미 만료된 채 대기 중이었을 수 있어
      신뢰할 수 없음을 테스트 docstring에 남겼다) `_cosine_similarity`
      호출이 실제로 메인(이벤트 루프) 스레드가 아닌 다른 스레드에서
      일어나는지 `threading.current_thread()`로 직접 확인한다 - `git
      stash`로 서비스 수정만 되돌리면 정확히 이 assert가 실패하는 것까지
      확인했다. 전체 372개 테스트 통과, 전체 커버리지 99%(`rag_service.py`
      100% 유지), mypy 클린. 검색 결과 자체(순위/정확도)는 전혀 바뀌지
      않는 순수 실행 위치 변경이라 모델/스키마 변경이나 마이그레이션,
      `FRONTEND_INTEGRATION.md` 갱신 모두 필요 없었다.

## 백로그 (91라운드)

- [x] 115. 로그인/가입/비밀번호 변경/게스트 승격/계정 삭제 때마다 bcrypt를
      이벤트 루프에서 그대로 호출해, 그 시간만큼 같은 워커의 다른 모든
      동시 요청(다른 사용자 요청, 진행 중인 WebSocket 스트림 포함)이
      멈추던 문제 수정 - 서브에이전트에게 90번 라운드가 rag_service.py에
      적용한 "이벤트 루프를 막는 CPU 바운드 작업" 패턴을 다른 곳에서도
      찾아보라고 명시적으로 지시했고, 89~90번 라운드가 남긴 후보들
      (모델 목록 API 인증/레이트리밋 누락, 헬스체크 타임아웃 - 이번에
      실제로 확인해보니 `OllamaService`가 이미 60초 타임아웃을 갖고 있어
      무한 대기는 아님을 확인하고 기각)보다 이게 더 실제적이고 심각하다고
      판단해 골랐다. `app/core/password.py`의 `hash_password`/
      `verify_password`는 내부적으로 `bcrypt.hashpw`/`bcrypt.checkpw`를
      호출하는데, 이 환경에서 직접 측정해보니 호출당 약 300ms가 걸린다
      (bcrypt는 무차별 대입 공격을 늦추기 위해 의도적으로 비용이 큰
      함수다). `auth_service.py`의 `signup`/`login`, `user_service.py`의
      `update_profile`/`upgrade_guest`/`delete_account` - 총 6곳의 호출부
      전부가 이 동기 함수를 `async def` 서비스 메서드 안에서 `await` 없이
      그대로 불러, 90번 라운드의 RAG 채점 문제와 완전히 같은 방식으로
      이벤트 루프를 300ms씩 점유했다. 다만 이번엔 사용 기록이 쌓여야
      나빠지는 문제가 아니라, 이 앱에서 가장 트래픽이 많은 로그인/가입
      경로에서 매 호출마다 무조건 발생한다는 점에서 더 심각하다. 검색
      결과(순위/정확도)를 바꾸지 않고 실행 위치만 옮긴 90번 라운드와
      똑같은 원칙으로, `password.py`의 순수 함수들은 그대로 두고 6개
      호출부 전부를 `await asyncio.to_thread(hash_password, ...)` /
      `await asyncio.to_thread(verify_password, ...)`로 감쌌다(로그인의
      "이메일 존재 여부와 무관하게 항상 bcrypt를 호출해야 하는" 타이밍
      공격 방어 로직은 호출 위치만 스레드로 옮겼을 뿐 두 분기 모두 여전히
      같은 방식으로 호출되므로 그대로 유지된다). 회귀 테스트는 90번
      라운드와 같은 원칙(시간차 기반 측정은 신뢰할 수 없음)으로,
      `hash_password`/`verify_password` 호출이 실제로 메인(이벤트 루프)
      스레드가 아닌 스레드 풀에서 일어나는지 `threading.current_thread()`로
      직접 확인하는 테스트 두 개를 추가했다 -
      `test_signup_and_login_hash_and_verify_password_off_the_event_loop_thread`
      (auth_service.py, signup+login)와
      `test_update_profile_and_delete_account_hash_and_verify_password_off_the_event_loop_thread`
      (user_service.py, update_profile+delete_account, 두 함수 모두 커버).
      `git stash`로 서비스 수정만 되돌리면 두 테스트 모두 정확히 이
      assert에서 실패하는 것까지 확인했다. 전체 374개 테스트 통과, 전체
      커버리지 99%(`user_service.py` 100% 유지, `auth_service.py`의
      유일한 미커버 라인은 이 라운드와 무관한 기존 방어적 분기), mypy
      클린. 순수 실행 위치 변경이라 모델/스키마 변경이나 마이그레이션,
      `FRONTEND_INTEGRATION.md` 갱신 모두 필요 없었다.

## 백로그 (92라운드)

- [x] 116. 오답노트(`GET /quizzes/wrong-answers`)에만 페이지네이션이 전혀
      없어, 계정이 오래될수록(틀린 문제가 쌓일수록) 응답 크기가 무한정
      늘어나던 문제 수정 - 서브에이전트에게 90~91번 라운드가 찾아낸
      "이벤트 루프를 막는 블로킹 호출" 패턴을 계속 찾아보라고 지시했지만,
      `time.sleep`/`requests.`/동기 파일 I/O 등을 전부 훑어봐도 더는 새
      사례가 없음을 확인했고(그 패턴은 이번 세션에서 소진됐다고 결론),
      대신 목록 API 전반의 일관성을 점검하다 이 항목을 새로 찾았다.
      `list_quizzes`/`list_reviews`/`list_sessions`/`list_practice_sessions`
      전부 `limit`(기본 20, 최대 100)/`offset` 쿼리 파라미터를 받고
      `X-Total-Count` 응답 헤더로 총 개수를 알려주는 동일한 패턴을 쓰는데,
      `get_wrong_answer_notebook`(`app/services/quiz_service.py`)만
      `LIMIT` 없이 "사용자의 모든 퀴즈에서 틀린 문제 전부"를 한 번에
      가져오고 있었다 - 이 뷰는 "가장 최근 퀴즈"가 아니라 "지금까지 틀린
      문제 전체"라 정리/만료 로직도 없어, 계정이 오래될수록(94번
      라운드가 다른 목록들에 페이지네이션을 넣을 때도 놓친 곳이다) 응답
      본문과 그 근거가 되는 3중 조인(Quiz × QuizAttempt × QuizAnswer ×
      QuizQuestion) 쿼리의 작업 집합이 함께 무한정 커진다. 다른 목록
      API와 완전히 같은 패턴으로 맞췄다: `get_wrong_answer_notebook`이
      `limit`/`offset`을 받고 `(entries, total)`을 반환하도록 바꿔, 기존
      조인 쿼리를 `base_query`로 분리한 뒤 `select(func.count())
      .select_from(base_query.subquery())`로 총 개수를 구하고, 실제
      데이터 조회에만 `.limit()/.offset()`을 붙였다. 라우트
      (`app/api/v1/routes/quiz.py`)도 다른 목록 엔드포인트와 동일하게
      `Query(default=20, ge=1, le=100)`/`Query(default=0, ge=0)`를 받고
      `response.headers["X-Total-Count"]`를 채우도록 맞췄다. 기존 회귀
      테스트(`test_get_wrong_answer_notebook_issues_a_constant_number_of_
      queries`, 퀴즈가 N개여도 SELECT가 고정 횟수만 나가는지 확인하던
      테스트)는 총 개수 COUNT 쿼리가 하나 늘어난 걸 반영해 "고정 2번"으로
      갱신했고(퀴즈 개수와 무관하게 여전히 고정 횟수라는 핵심 속성은
      그대로 유지), `test_list_quizzes_pagination`과 동일한 형태의
      `test_wrong_answer_notebook_pagination`을 새로 추가해 `limit`/
      `offset`/`X-Total-Count`가 실제로 동작하고 페이지 간 항목이 겹치지
      않는지 확인했다 - `git stash`로 서비스/라우트 수정만 되돌리면 두
      테스트 모두(새 테스트는 `X-Total-Count` 불일치로, 기존 테스트는
      `limit`/`offset` 키워드 인자를 모르는 `TypeError`로) 정확히
      실패하는 것까지 확인했다. `docs/FRONTEND_INTEGRATION.md`의
      "별도 페이지네이션은 없음(개인 학습 데이터라 규모가 크지 않을
      거라 가정)"이라는 기존 문구가 이제 거짓이 되므로, 다른 목록
      API들과 같은 설명으로 갱신했다. 전체 375개 테스트 통과, 전체
      커버리지 99%(`quiz_service.py`/`routes/quiz.py` 100% 유지), mypy
      클린. 응답 형태가 그대로고(새 쿼리 파라미터는 전부 기본값이 있어
      기존 호출도 그대로 동작) 헤더 하나만 추가되는 하위 호환 변경이라
      마이그레이션은 필요 없었다.

## 백로그 (93라운드)

- [x] 117. 퀴즈 재도전 이력(`GET /quizzes/{id}/attempts`)에만 페이지네이션이
      없어, 같은 퀴즈를 반복 재도전할수록 응답 크기가 무한정 늘어나던
      문제 수정 - 92번 라운드가 오답노트에서 고친 것과 정확히 같은
      부류의 문제로, 서브에이전트에게 "다른 목록형 API 중에도 페이지네이션이
      빠진 형제가 있는지" 체계적으로 찾아보라고 지시해서 나온 결과다(같은
      라운드에서 이벤트 루프 블로킹 패턴을 다시 훑어봤지만 90~91번
      라운드가 이미 그 부류를 소진했음도 확인했다).
      `QuizAttemptRepository.list_for_quiz`가 `LIMIT` 없이 한 퀴즈에 대한
      전체 재도전 이력을 가져오고, `QuizService.list_attempts`와 라우트도
      그걸 그대로 반환하고 있었다 - 같은 퀴즈를 여러 번 다시 풀어보는 건
      학습 앱에서 아주 흔한 사용 패턴이라, 계정이 오래될수록(재도전
      횟수가 쌓일수록) 응답과 그 근거 쿼리가 함께 무한정 커진다.
      `InterviewPracticeSessionRepository.list_for_user`(이미 페이지네이션
      돼 있던 다른 목록 API)와 완전히 같은 패턴으로 맞췄다:
      `list_for_quiz`가 `limit`/`offset`을 받고 `submitted_at`이 같은
      행 사이의 순서가 페이지마다 흔들리지 않도록 `id`를 2차 정렬
      기준으로 추가했고, 별도로 `count_for_quiz`를 만들어 총 개수를
      구했다. `QuizService.list_attempts`가 `(attempts, total)`을
      반환하도록 바꾸고, 라우트(`app/api/v1/routes/quiz.py`)도 다른
      목록 엔드포인트와 동일하게 `Query(default=20, ge=1, le=100)`/
      `Query(default=0, ge=0)`를 받고 `X-Total-Count` 응답 헤더를
      채우도록 맞췄다(데이터 export가 쓰는 `list_for_user`는 "전체가
      목적"인 별개 메서드라 그대로 뒀다). 기존 테스트
      (`test_list_attempts_returns_full_history_newest_first` 등)는 그대로
      통과했고, `test_list_quizzes_pagination`/92번 라운드의
      `test_wrong_answer_notebook_pagination`과 동일한 형태로
      `test_list_attempts_pagination`을 새로 추가해 `limit`/`offset`/
      `X-Total-Count`가 실제로 동작하고 페이지 간 항목이 겹치지 않는지
      확인했다(중복 제출 방지에 걸리지 않도록 매번 다른 답안 조합으로
      4번 재도전) - `git stash`로 리포지토리/서비스/라우트 수정만
      되돌리면 이 새 테스트가 `X-Total-Count` 헤더 부재로 정확히
      실패하는 것까지 확인했다. `docs/FRONTEND_INTEGRATION.md`의
      "재도전 이력 전체"라는 문구도 다른 목록 API들과 같은 설명으로
      갱신했다. 전체 376개 테스트 통과, 전체 커버리지 99%
      (`quiz_attempt_repository.py`/`quiz_service.py`/`routes/quiz.py`
      모두 100% 유지 - 참고로 이 라운드가 건드리지 않은
      `user_service.py`가 이번 전체 실행에서 95%로 나왔는데, 확인해보니
      이 라운드와 무관한 기존 동시성 레이스 테스트
      (`test_concurrent_email_change_to_same_email_yields_clean_conflict_
      not_crash`)가 진짜 `asyncio.gather` 레이스라 어느 쪽이 IntegrityError
      분기를 타는지가 실행마다 달라지는, 이전부터 있던 커버리지 플레이키함
      이었다 - 격리 실행으로 재현까지 확인했고 이 라운드가 만든 회귀는
      아니다), mypy 클린. 응답 형태가 그대로고 새 쿼리 파라미터는 전부
      기본값이 있어 기존 호출도 그대로 동작하는 하위 호환 변경이라
      마이그레이션은 필요 없었다.

## 백로그 (94라운드)

- [x] 118. 학습챗 메시지 전송/스트리밍이 매 턴마다 세션의 전체 메시지
      히스토리를 DB에서 통째로 읽어온 뒤 파이썬에서 최근 N개만 자르고
      있어, 대화가 길어질수록(메시지 수 제한 없음) 실제로 쓰지도 않을
      과거 메시지까지 매번 다시 읽어오는 낭비가 계속 커지던 문제 수정 -
      92~93번 라운드의 "리포지토리 목록 메서드 중 페이지네이션 없는
      형제 찾기" 스윕을 서브에이전트에게 계속 시켜서 나온 결과다(모든
      리포지토리의 `list_*`/전체 조회 메서드 18개를 전수 점검했고,
      export처럼 "전체가 목적"인 메서드를 빼면 새로 남은 건 이 항목과
      `KnowledgeChunkRepository.list_for_user`뿐이었는데, 후자는 90번
      라운드가 이미 CPU 블로킹 쪽은 고쳤고 나머지는 아직 개선 여지가
      있는 수준이라 이번엔 더 심각한 이 항목을 골랐다). `study_service.py`의
      `send_message`/`stream_message`는 `StudyMessageRepository.
      list_for_session()`으로 세션 전체 메시지를 가져온 뒤, `_recent_history()`
      헬퍼로 `MAX_CHAT_HISTORY_MESSAGES`(기본 40)개만 파이썬 슬라이싱으로
      남기고 나머지는 버렸다 - 한 세션에서 계속 대화하는 건 학습 앱에서
      아주 흔한 사용 패턴이라, 세션이 오래될수록(메시지가 수백~수천 개로
      쌓일수록) 채팅 한 턴을 처리할 때마다 그 전체를 DB에서 읽어오는 게
      점점 더 낭비가 된다 - 90/91번 라운드가 고친 "매 요청마다 커지는
      비용" 문제와 같은 성격이지만, 이번엔 CPU가 아니라 불필요한 DB
      조회량이 문제다. `StudyMessageRepository`에 `list_recent_for_session
      (session_id, limit)`을 새로 만들어 `ORDER BY created_at DESC LIMIT`으로
      필요한 만큼만 가져온 뒤 시간순으로 다시 뒤집게 했고(다른
      `list_for_user`들처럼 `id`를 2차 정렬 기준으로 추가해 같은 요청
      안에서 몇 ms 사이에 만들어지는 메시지 쌍처럼 created_at이 같은
      행 사이의 순서가 잘림 경계에서 흔들리지 않게 했다), `send_message`/
      `stream_message`가 이 메서드를 직접 쓰도록 바꿔 이제 더는 세션 전체를
      읽지 않는다. `_recent_history()` 파이썬 헬퍼는 필요 없어져 삭제했다.
      `GET /study/sessions/{id}`가 세션 상세와 함께 메시지 전체를 페이지네이션
      없이 반환하는 것도 같은 스윕에서 눈에 띄었지만, `QuizDetailResponse.
      questions`/`InterviewPracticeSessionDetailResponse.turns`도 똑같이
      "단일 리소스 상세 조회는 하위 항목 전체를 반환"하는 이 코드베이스
      전체의 일관된 설계라(목록 API만 페이지네이션 대상), 이 라우트만
      따로 페이지네이션을 넣으면 오히려 기존 설계 원칙과 어긋나는
      비일관성이 생긴다고 판단해 이번 라운드에서는 손대지 않기로
      결정했다 - 별도 항목으로 남겨둘 만한 가치는 있지만 이번엔 범위
      밖으로 뒀다. 새 메서드에 대한 단위 테스트
      (`test_list_recent_for_session_returns_last_n_in_chronological_order`)를
      추가해 최근 N개/limit=0/음수/전체보다 큰 limit 경계값을 실제 DB
      조회로 확인했다 - `created_at`이 `server_default=func.now()`라 SQLite
      에서는 짧은 시간에 여러 메시지를 만들면 값이 쉽게 동률이 나는데,
      순서 검증을 흔들리지 않게 하려고 각 메시지의 `created_at`을 명시적으로
      서로 다른 값으로 지정해서 만들었다(처음엔 이 동률 때문에 실제로
      테스트가 예상과 다른 순서를 반환하는 걸 직접 목격했고, 그걸 계기로
      `id` 2차 정렬 기준을 추가하게 됐다 - id는 무작위 UUID라 순서 검증에는
      못 쓰지만 동률을 결정론적으로만 깨면 되는 용도로는 충분하다). `git
      stash`로 리포지토리/서비스 수정만 되돌리면 새 테스트가
      `AttributeError`로 정확히 실패하는 것까지 확인했다. 기존
      `test_send_message_truncates_history_to_configured_limit`/
      `test_stream_message_truncates_history_to_configured_limit`(HTTP
      레벨에서 실제로 Ollama에 전달되는 메시지 개수/내용을 확인하던 테스트)도
      수정 없이 그대로 통과해, 관측 가능한 채팅 동작 자체는 전혀 바뀌지
      않았음을 확인했다. 전체 376개 테스트 통과, 전체 커버리지 99%
      (`study_service.py`/`study_message_repository.py` 모두 100% 유지 -
      `user_service.py`의 95%는 93번 라운드에서 이미 확인한, 이 라운드와
      무관한 기존 동시성 레이스 테스트의 커버리지 플레이키함), mypy 클린.
      순수 리포지토리/서비스 계층 최적화라 모델/스키마 변경이나 마이그레이션,
      `FRONTEND_INTEGRATION.md` 갱신 모두 필요 없었다.

## 백로그 (95라운드)

- [x] 119. RAG 검색(`retrieve_relevant`)이 매 학습챗/면접연습 턴마다 사용자의
      색인된 청크 "전체"를 DB에서 읽어와 후보로 삼아, 계정이 오래될수록
      (색인엔 만료/정리 로직이 없음) 그 조회량 자체가 무한정 커지던 문제에
      안전장치 추가 - 92~94번 라운드의 "페이지네이션 없는 리포지토리 목록
      메서드 찾기" 스윕에서 마지막으로 남아있던 항목이다(전체 리포지토리
      `list_*` 계열 18개를 다 훑었고, export 전용 메서드를 빼면 이게
      마지막 미해결 사례였음을 재확인했다). `KnowledgeChunkRepository.
      list_for_user`에 `LIMIT`이 없었고, 90번 라운드는 이미 이 후보들을
      채점하는 CPU 작업 자체는 스레드로 옮겼지만(이벤트 루프 안 막음),
      후보를 통째로 읽어오는 조회량 자체는 그대로였다. 다만 이 항목은
      단순히 "LIMIT을 건다"로 끝나지 않는 게, RAG는 원래 "가장 관련
      있는" 자료를 찾는 게 목적이라 최신순으로 자르면 오래됐지만 더
      관련 있을 자료가 검색 대상에서 조용히 빠질 수 있다는 트레이드오프가
      있다 - 이 저장 방식 자체가 `knowledge_chunk.py` 모델 주석에 이미
      "청크가 수천 개 넘어가면 pgvector 전환 고려"라고 적혀 있는 임시
      설계라, 진짜 근본 해결(DB 벡터 인덱스로 옮겨 유사도 검색 자체를
      DB가 top-K만 돌려주게 하는 것)은 새 익스텐션/컬럼 타입/마이그레이션이
      필요한 별도 프로젝트 규모라 이번 라운드 범위를 벗어난다고 판단했다.
      대신 이 세션에서 이미 같은 절충을 실제로 쓰고 있는 선례(퀴즈 생성이
      학습 세션 소스가 너무 길면 "가장 최근 대화만 남기고 앞부분을 조용히
      자르는" `max_quiz_source_length`)를 그대로 따라, 정상적인 사용량보다
      훨씬 크게 잡은 넉넉한 상한(`RAG_MAX_CANDIDATE_CHUNKS`, 기본 2000)을
      새 설정으로 추가해 극단적으로 커진 계정에 대한 최후 방어선 역할만
      하게 했다 - 현실적인 계정 규모에서는 사실상 영향이 없고, 이 상한에
      자주 걸릴 정도로 데이터가 쌓이면 그 자체가 pgvector 전환이 필요하다는
      신호로 보면 된다는 점을 설정 주석에 명시했다. `list_for_user`가
      `limit` 파라미터를 받아 `ORDER BY created_at DESC LIMIT`으로
      최근 것부터 가져오도록 바꿨고(`id`를 2차 정렬 기준으로 추가해
      같은 요청 안에서 거의 동시에 색인되는 user/assistant 메시지 쌍처럼
      created_at이 같은 행 사이의 잘림 경계가 흔들리지 않게 함 - 94번
      라운드와 같은 이유), `RagService.retrieve_relevant`가 이 상한을
      넘겨준다. 회귀 테스트
      (`test_list_for_user_limits_to_most_recent_chunks`)는 청크 5개를
      만든 뒤 limit=3이면 최신 3개만, limit=100이면 전부(5개) 반환하는지
      실제 DB 조회로 확인했다 - `created_at`이 `server_default`라 짧은
      시간에 여러 청크를 만들면 동률이 나기 쉬워서(94번 라운드와 같은
      함정), 각 청크의 `created_at`을 명시적으로 서로 다른 값으로
      지정해 순서 검증이 흔들리지 않게 했다. `git stash`로 리포지토리/
      서비스/설정 수정만 되돌리면 새 테스트가 `limit` 키워드 인자를
      모르는 `TypeError`로 정확히 실패하는 것까지 확인했다(같은 이유로
      `list_for_user`를 직접 호출하던 기존 테스트 하나도 `limit=` 인자를
      추가해 갱신). 전체 377개 테스트 통과, 전체 커버리지 99%
      (`config.py`/`rag_service.py`/`knowledge_chunk_repository.py` 모두
      100% 유지 - `user_service.py`도 이번엔 100%로 돌아와, 93번
      라운드에서 확인한 게 진짜 플레이키함이었음을 다시 한번 확인했다),
      mypy 클린. 새 설정값(기본값 있음, `.env.example`에도 추가) 추가와
      순수 조회 범위 제한이라 모델/마이그레이션이나 `FRONTEND_INTEGRATION.md`
      갱신은 필요 없었다.

## 백로그 (96라운드)

- [x] 120. Redis 장애 중 WebSocket 스트리밍(학습챗/면접복기)의 수동 레이트리밋
      (`check_rate_limit`)이 REST 엔드포인트와 달리 인메모리 폴백으로 전혀
      전환되지 않고 장애 기간 내내 완전 무제한으로 허용되던 문제 수정 -
      "아직 안 깊게 감사한 영역" 목록에 여러 라운드째 이름만 올라 있던
      `app/core/rate_limit.py`를 서브에이전트에게 이번엔 실제로 slowapi
      내부 구현(`.venv/.../slowapi/extension.py`)까지 직접 읽고 검증하라고
      지시해서 나온 결과다. `check_rate_limit()`은 `limiter.limiter`(내부
      저장소 전략 객체)를 직접 호출하는데, slowapi의 `in_memory_fallback_
      enabled` 자동 전환은 그 프로퍼티가 `_storage_dead`일 때만 인메모리
      폴백을 돌려주는 방식으로 동작하고, `_storage_dead`는 slowapi 안에서
      `@limiter.limit()` 데코레이터 경로(`_check_request_limit`)에서만
      세팅된다는 걸 실제 소스로 확인했다 - `check_rate_limit()`은 그
      경로를 거치지 않으므로 Redis가 죽어도 이 플래그를 절대 스스로
      세우지 못하고, `RedisError`를 잡아 그냥 "허용"만 무한정 반복했다
      (우연히 같은 시점에 다른 HTTP 요청이 그 플래그를 건드려주지 않는
      한). 그 결과 REST 엔드포인트들은 Redis 장애 중에도(여러 워커 간
      정확도는 떨어져도) 인메모리 카운터로 계속 제한되는데, 정작 가장
      호출 비용이 큰 두 WebSocket 스트리밍 경로만 장애 기간 내내 완전
      무제한이 되는 비일관성이 있었다 - 이 함수를 처음 만든 이전 라운드도
      "자동 복구 로직을 안 거친다"는 사실 자체는 문서화·테스트해뒀지만
      ("레이트리밋 자체보다 서비스 가용성이 우선"이라는 의도만 확인했지),
      그게 구체적으로 "완전 무제한"을 뜻한다는 것까지는 짚지 않았던
      것으로 보인다 - 이미 설정하고 비용까지 지불한 인메모리 폴백
      인프라를 WebSocket 경로에도 똑같이 적용해 REST와 일관되게 맞추는
      게 합리적인 개선이라고 판단해 다시 열었다. `RedisError`를 잡으면
      slowapi가 스스로 하는 것과 똑같이 `limiter._storage_dead = True`를
      직접 세운 뒤 재시도하도록 고쳤다 - 이제 처음 감지 시점부터 실제
      인메모리 폴백 카운터로 제한이 이어지고, 폴백 자체가 실패하는(사실상
      있을 수 없는) 경우에만 기존처럼 "허용"으로 안전하게 처리한다. 기존
      테스트(`test_check_rate_limit_allows_request_when_redis_unreachable`,
      예전 동작을 문서화하던 테스트)는 "첫 호출은 폴백 전환 전이라
      허용된다"는 의미로 다시 쓰고, Redis가 죽은 채로 한도(2/minute)를
      실제로 넘기면 세 번째 호출부터 거부되는지 확인하는
      `test_check_rate_limit_falls_back_to_in_memory_limiting_when_redis_dead`
      를 새로 추가했다 - `git stash`로 수정만 되돌리면 이 새 테스트가
      "세 호출 다 허용됨"으로 정확히 실패하는 것까지 확인했다. 이
      테스트만으로는 재시도 블록 내부의 "이미 한도 초과" 분기와
      "폴백 자체 실패" 분기가 커버리지에서 빠지는 걸 발견해(폴백 전환
      후에는 바깥쪽 try가 재시도 없이 바로 성공/실패하기 때문), 폴백
      리미터를 미리 한도까지 채워둔 뒤 Redis 장애를 처음 감지하는 순간
      곧바로 거부가 나오는지 확인하는
      `test_check_rate_limit_denies_immediately_when_fallback_already_at_limit`
      와, 폴백 자체를 몽키패치로 실패시켜도 예외 없이 "허용"으로 안전하게
      처리되는지 확인하는
      `test_check_rate_limit_allows_when_fallback_itself_fails`를 추가로
      더했다. 전체 380개 테스트 통과, 전체 커버리지 99%(`rate_limit.py`
      100% 유지), mypy 클린. 순수 내부 로직 수정이라 모델/스키마 변경이나
      마이그레이션은 필요 없었고, 클라이언트가 관측하는 변화는 "Redis
      장애 중에도 WebSocket이 REST처럼 계속 제한된다"는 것뿐이라
      `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (97라운드)

- [x] 121. 모델 목록 API(`GET /models`)에 레이트리밋이 전혀 없고, 캐시가 막
      만료된 순간 동시에 온 요청들이 락 없이 각자 독립적으로 Ollama를
      호출하던 문제 수정 - 8라운드 가까이 "남은 후보 중 그나마 나은 것"으로
      계속 뒤로 밀렸던 항목인데, 이번엔 서브에이전트에게 "아직 안 읽어본
      파일 목록에 이름만 올리지 말고 실제로 읽으라"고 지시해서
      `core/cache.py`/`core/scheduler.py`/`core/security.py`/
      `core/dependencies.py`/`db/session.py`/`export_service.py`/
      `rag_backfill_service.py`/`chat.py`/면접복기 WebSocket 라우트를
      전부 훑었지만 더 심각한 새 문제는 없었고, 결국 계속 밀려온 이
      항목이 여전히 최선이라는 걸 재확인한 뒤 골랐다. `/models`는 민감
      정보가 아니라 의도적으로 인증 없이 공개돼 있는데(코드 주석에
      명시), 이 앱에서 유일하게 인증이 없는 만큼 익명 호출자를 막을
      다른 수단이 레이트리밋뿐이었다 - 그런데 그것마저 전혀 없었다.
      60초 `TTLCache`가 있어 대부분은 막히지만, (a) 캐시가 있어도 반복
      호출 자체를 막지는 못하고 (b) `TTLCache.get`/`set`엔 락이 없어서
      캐시가 막 만료된 순간 동시에 들어온 요청들은 전부 캐시 미스를
      겪어 각자 독립적으로 `ollama_service.list_models()`를 호출한다
      (캐시가 있는 의미가 없어지는 몰림) - 두 구멍 다 이 60초 캐시를
      사실상 무력화할 수 있었다. 다른 레이트리밋들(`chat_rate_limit`/
      `auth_rate_limit`/`export_rate_limit`)과 같은 패턴으로
      `models_rate_limit`(기본 30/minute - LLM 호출이 아니라 캐시된
      목록 조회라 `chat_rate_limit`보다 넉넉하게 잡음) 설정을 추가하고
      기존 검증기에 함께 등록했다. 캐시 미스 몰림은 `asyncio.Lock`으로
      막았다 - 캐시가 비어있으면 락을 잡고, 락을 얻은 뒤 다시 한번
      캐시를 확인해(락을 기다리는 동안 다른 요청이 이미 채워놨을 수
      있음) 그래도 비어있을 때만 실제로 Ollama를 부르고 채운다. 레이트
      리밋 데코레이터/`Request`/`Response` 배선 없이 이 캐시/락 동작만
      직접 테스트할 수 있도록 `_get_or_fetch_models()`로 로직을
      분리했다(부수적으로, 라우트 안에서 `Response`(FastAPI 파라미터)와
      이름이 겹치던 지역 변수 `response`(캐시에 넣을
      `OllamaModelListResponse`)도 이번에 갈라놔 헷갈림을 없앴다 -
      slowapi가 헤더 주입 시 함수 반환값이 아니라 원래 kwargs에서
      `response`를 다시 꺼내 쓰는 구조라 실제 버그는 아니었지만
      가독성 문제였다). 회귀 테스트는 두 가지: `test_list_models_is_
      rate_limited`(다른 라우트들의 레이트리밋 테스트와 같은 패턴,
      `MODELS_RATE_LIMIT=2/minute`로 세 번째 호출이 429인지 확인)와
      `test_get_or_fetch_models_coalesces_concurrent_cache_misses`
      (`_get_or_fetch_models`를 5개 동시에 `asyncio.gather`로 호출해도
      실제 Ollama 호출은 정확히 1번만 일어나는지 확인, 겹칠 시간을
      벌기 위해 가짜 Ollama 서비스에 짧은 `asyncio.sleep` 포함) - `git
      stash`로 라우트/설정 수정만 되돌리면 첫 번째 테스트는 세 번째
      호출도 200이 나와서, 두 번째 테스트는 `_get_or_fetch_models`가
      없어 `ImportError`로 정확히 실패하는 것까지 확인했다. 전체 382개
      테스트 통과, 전체 커버리지 99%(`routes/models.py`/`config.py`
      모두 100% 유지), mypy 클린. 새 설정값(기본값 있음, `.env.example`
      에도 추가) 추가와 순수 방어 로직이라 모델/마이그레이션은 필요
      없었고, 정상적인 사용 패턴(캐시 안에서의 반복 조회)은 그대로라
      `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (98라운드)

- [x] 122. 활성 세션 목록 API(`GET /auth/sessions`)에만 레이트리밋이 없고
      페이지네이션도 없어, 반복 로그인할수록 응답이 무한정 커지던 문제
      수정 - 서브에이전트가 처음 제시한 최우선 후보는 사실
      `GET /study/sessions/{id}`의 메시지 히스토리 페이지네이션이었는데,
      이건 94번 라운드가 이미 "단일 리소스 상세 조회는 하위 항목 전체를
      반환한다"는 이 코드베이스의 일관된 설계(퀴즈 문항/면접연습 turns도
      동일)라고 판단해 의도적으로 보류한 항목이었다 - 이번 라운드의
      서브에이전트 프롬프트에서 그 보류 이력을 실수로 빼먹어 다시 후보로
      나온 것이었다. 직접 `docs/FRONTEND_INTEGRATION.md`를 확인해보니
      "GET /study/sessions/{id}로 조회되는 전체 메시지 히스토리 자체는
      그대로 다 보존된다"는 문구로 이미 프론트에 공개 문서화된 계약이라,
      지금 페이지네이션을 넣으면 기존 계약을 깨는 하위 호환성 문제까지
      생긴다고 판단해 재차 보류하고, 서브에이전트의 2순위 후보였던 이
      항목을 대신 골랐다. `app/api/v1/routes/auth.py`를 보면
      `signup`/`login`/`guest`/`refresh`/`logout`/`revoke_session`/
      `revoke_all_sessions` 전부 `@limiter.limit(auth_rate_limit)`이
      걸려 있는데 `list_sessions`(`GET /auth/sessions`)만 빠져 있었다.
      로그인은 매번 새 refresh token을 발급하고 명시적으로 로그아웃하기
      전까지는 폐기되지 않는(여러 기기 동시 로그인 지원을 위한 설계)
      구조라, `AUTH_RATE_LIMIT`(기본 분당 5회) 한도로 반복 로그인하면
      `REFRESH_TOKEN_EXPIRE_DAYS`(기본 14일) 동안 활성 세션이 계속
      쌓이는데, 그걸 페이지네이션 없이 한 번에 반환하는 이 엔드포인트
      자체엔 반복 호출을 막을 제한도 전혀 없었다 - 이 계정 자체에만
      영향을 주는(자해성) 문제라 QuizDetailResponse류와 달리 심각도는
      낮지만, 92/93번 라운드가 이미 두 번 고친 것과 정확히 같은
      "형제 목록 API만 페이지네이션이 빠짐" 패턴이라 근거가 명확했다.
      `RefreshTokenRepository.list_active_for_user`가 `limit`/`offset`을
      받고(다른 목록들처럼 `created_at`이 같은 행의 순서가 흔들리지
      않도록 `id`를 2차 정렬 기준으로 추가) `count_active_for_user`를
      새로 만들었고, `AuthService.list_active_sessions`이
      `(sessions, total)`을 반환하도록 바꿨다. 라우트도 다른
      `/auth/*`와 동일하게 `@limiter.limit(auth_rate_limit)`을 추가하고
      `Query(default=20, ge=1, le=100)`/`Query(default=0, ge=0)`를 받아
      `X-Total-Count` 헤더를 채우도록 맞췄다. 회귀 테스트는
      `test_list_sessions_pagination`(로그인 3회로 활성 세션 4개를
      만든 뒤 `limit`/`offset`/`X-Total-Count`가 실제로 동작하고 페이지
      간 항목이 겹치지 않는지 확인)과 `test_list_sessions_is_rate_limited`
      (다른 라우트들의 레이트리밋 테스트와 같은 패턴, `AUTH_RATE_LIMIT=
      2/minute`로 세 번째 호출이 429인지 확인)를 추가했다 - `git stash`
      로 리포지토리/서비스/라우트 수정만 되돌리면 두 테스트 모두 정확히
      실패하는 것까지 확인했다(테스트 헬퍼에서 구식 시그니처로
      `list_active_for_user`를 직접 호출하던 기존 동시성 테스트 하나도
      `limit=20, offset=0`을 추가해 갱신). `docs/FRONTEND_INTEGRATION.md`
      의 세션 관리 절에 페이지네이션/레이트리밋 설명을 추가했다(여기는
      기존에 "전체 반환" 계약이 문서화돼 있지 않았으므로 하위 호환성
      문제가 없다). 전체 384개 테스트 통과, 전체 커버리지 99%
      (`refresh_token_repository.py`/`routes/auth.py` 모두 100% 유지,
      `auth_service.py`의 유일한 미커버 라인은 이 라운드와 무관한 기존
      방어적 분기), mypy 클린. 응답 형태가 그대로고 새 쿼리 파라미터는
      전부 기본값이 있어 기존 호출도 그대로 동작하는 하위 호환 변경이라
      마이그레이션은 필요 없었다.

## 백로그 (99라운드)

- [x] 123. 학습챗/면접복기 WebSocket 스트리밍이 동시 연결 수에 아무 상한이
      없어, 클라이언트가 연결을 계속 열기만 해도(방치가 아니라 정상적으로
      메시지를 주고받는 활성 연결이어도) DB 커넥션 풀 전체가 고갈될 수
      있던 문제 수정. `app/db/session.py`의 `get_db()`는 FastAPI yield
      의존성이라 `Depends(get_study_service)`/`Depends(get_interview_review_service)`
      를 통해 WebSocket 라우트에서 쓰이면 연결이 accept된 순간부터 완전히
      끊어질 때까지 커넥션 풀의 커넥션 하나를 계속 점유한다(메시지 하나
      처리할 때만 잠깐 빌리는 HTTP 요청과 다르다) - `create_async_engine`에
      하드코딩된 `pool_size=5, max_overflow=5`(합쳐서 10, `Settings`로
      노출돼 있지도 않음)보다 많은 동시 WS 연결이 열리면 이 라우트뿐
      아니라 앱의 다른 모든 HTTP/WebSocket 요청까지 막힌다. 기존에 있던
      `ws_idle_timeout_seconds`는 "방치된" 연결이 풀을 계속 붙잡는 것만
      막을 뿐, 활발히 메시지를 주고받는 정상적인 동시 연결이 풀 용량을
      넘겨 열리는 것까지는 막지 못해 - 이번 항목은 그 보완책이다.
      `Settings.max_concurrent_ws_connections: int = 6`(풀 용량 10보다
      낮게 잡아 일반 HTTP 트래픽이 쓸 여유를 남김)을 추가하고,
      `app/core/dependencies.py`에 모듈 전역 `_active_ws_connections`
      카운터 + `asyncio.Lock`으로 지키는 `limit_ws_connections` 의존성을
      새로 만들었다 - accept 전에 상한을 넘었으면 `get_current_user_ws`와
      같은 방식으로 `WebSocketException(code=WS_1013_TRY_AGAIN_LATER)`을
      던져 접속 자체를 거부하고, 정상 처리된 연결은 `finally`에서 슬롯을
      반납한다. `study.py`/`interview_review.py` 두 스트리밍 라우트 모두
      첫 번째 파라미터로 `_connection_slot: None = Depends(limit_ws_connections)`
      를 추가해 같은 카운터를 공유하게 했다(라우트별로 따로 세지 않고
      앱 전체에서 합산 - 두 라우트가 같은 DB 풀을 나눠 쓰기 때문에
      이래야 실제 위험을 정확히 반영한다). `tests/conftest.py`의
      `_reset_state`에 `reset_ws_connection_counter()`를 추가해 테스트
      간 카운터를 격리했다. 회귀 테스트 4개: `test_study.py`에
      `test_stream_message_rejects_when_at_max_concurrent_connections`
      (상한을 1로 낮추고 연결 하나를 열어둔 채 두 번째 연결을 시도하면
      바로 거부되는지)와 `test_stream_message_accepts_new_connection_after_previous_one_closes`
      (첫 연결이 정상 종료되면 슬롯이 반납돼 다음 연결은 같은 상한
      아래서도 받아들여지는지 - 카운터가 증가만 하고 줄어들지 않는
      회귀가 없는지 확인), `test_interview_review.py`에 같은 패턴의
      거부 테스트와 `test_max_concurrent_ws_connections_is_shared_across_study_and_review_routes`
      (학습챗 라우트에서 연결을 하나 열어둔 상태로 면접복기 라우트의
      새 연결을 시도하면 역시 거부되는지 - 카운터가 라우트별이 아니라
      앱 전체 공유라는 게 이 기능의 핵심이라 이 테스트가 없으면 "그냥
      라우트마다 따로 세는" 훨씬 얕은(그리고 틀린) 구현으로도 다른
      테스트들은 다 통과했을 것이다). `git stash`로 의존성/설정/라우트
      수정만 되돌리면 거부 테스트가 응답 없이 타임아웃(행)되는 것으로
      차이를 확인했다 - 상한 로직 자체가 없으니 거부 이벤트가 영영
      오지 않아 `pytest.raises(WebSocketDisconnect)`가 기다리는 예외가
      발생하지 않고 무한 대기하는 게 올바른 관찰 결과였다.

      이번 라운드는 검증 단계에서 실제 테스트 인프라 버그를 하나
      더 잡았다: 전체 스위트(`--cov` 포함)가 `test_study.py`의
      `test_stream_message_accepts_new_connection_after_previous_one_closes`
      직후에서 실행할 때마다 멈췄는데, 정작 이 테스트 자체는 단독
      실행/파일 단위 실행에서는 항상 통과해서 처음엔 원인을 잘못
      짚었다(간헐적으로 느린 bcrypt 테스트와 착각해 타임아웃만 늘려
      재시도하기도 했다). `py-spy dump`로 실제로 멈춰 있는 프로세스의
      스택을 떠보고 나서야 정확한 위치를 확인했다 - `client` fixture의
      teardown(`TestClient.__exit__` → anyio 블로킹 포털 스레드
      `join()`)이 걸려 있었고, `pytest_runtestloop`의 아이템 인덱스가
      정확히 이 테스트를 가리켰다. 원인은 이 테스트의 "두 번째" WS
      연결이 `send_json` 후 `user_message` 이벤트 하나만 `receive_json`
      하고 나머지 `delta`/`delta`/`done` 이벤트를 받지 않은 채 명시적
      `close()`도 없이 `with` 블록을 빠져나갔던 것 - 세션 내내
      확립해 온 "WS 테스트는 반드시 끝까지 주고받고 명시적으로
      `close()`한다"는 컨벤션을 이 테스트의 첫 번째 연결(이전에 이미
      한 번 이 문제로 재작성됨)에는 적용했지만 두 번째 연결에는 빠뜨린
      것이었다 - 서버 쪽 핸들러가 스트리밍 도중에 멈춰 있어 포털
      스레드가 정상 종료하지 못했다. 두 번째 연결도 `delta`/`delta`/
      `done`을 마저 받고 `close()`하도록 고쳐서 해결했다(수정 후
      전체 스위트를 두 번 연속 클린하게 통과시켜 확인). 전체 388개
      테스트 통과, 전체 커버리지 99%(`app/core/dependencies.py`/
      `app/core/config.py`/`app/api/v1/routes/study.py`/
      `app/api/v1/routes/interview_review.py` 모두 100% - 테스트에서
      전혀 쓰이지 않던 디버그용 헬퍼 `active_ws_connections()`는
      죽은 코드라 제거), mypy 클린. 클라이언트가 새 에러 코드
      `1013`을 받을 수 있다는 점만 추가된 순수 확장 변경이라
      마이그레이션은 필요 없었다.

## 백로그 (100라운드)

- [x] 124. `QuizAttemptRepository.get_latest_for_quiz`(퀴즈 재제출 결과 조회
      `GET /quizzes/{id}/result`와 재제출 중복 감지의 기준점)만 `submitted_at`
      2차 정렬 기준 없이 `.scalars().first()`로 "최신 시도"를 고르던 문제
      수정. 바로 아래 `list_for_quiz`는 "submitted_at만으로 정렬하면 값이
      같은 행 사이의 순서가 SQL 표준상 정의되어 있지 않다"는 이유로 이미
      `id.desc()`를 2차 정렬 기준으로 쓰고 있었고, `QuizAttempt` 모델의
      `submitted_at` 필드 자체에도 "SQLite의 CURRENT_TIMESTAMP는 초 단위라
      같은 퀴즈를 짧은 간격으로 다시 제출하면 최신 제출을 구분 못 하는
      문제가 실제로 재현됐다"는 주석이 남아 있었다(그래서 마이크로초
      정밀도의 파이썬 쪽 기본값으로 바뀐 이력이 있음) - 그런데 정작
      `get_latest_for_quiz`만 이 동률 처리를 빠뜨리고 있었다. grep으로
      확인해보니 이 코드베이스에서 유일하게 `.scalars().first()`로 "최신
      1건"을 고르는 곳이기도 했다. 영향은 두 곳: `QuizService.get_latest_result`
      가 보여주는 문항별 정답 여부가 목록(`list_for_quiz`)의 1등 항목과
      다른 시도를 가리킬 수 있고, `_find_recent_duplicate_attempt`(재제출
      중복 감지 - 22라운드에서 만든 아이덴포턴시 보장)도 엉뚱한 "최신
      시도"와 비교하게 될 수 있었다. `list_for_quiz`와 똑같이
      `.order_by(QuizAttempt.submitted_at.desc(), QuizAttempt.id.desc())`
      로 맞췄다. 회귀 테스트(`test_quiz_submission_dedup.py`에
      `test_get_latest_for_quiz_breaks_submitted_at_ties_by_id`)는
      94라운드에서 확립한 "직접 모델 행을 구성해 동률 타임스탬프를
      강제로 만드는" 기법을 그대로 썼다 - 리포지토리의 `create()`를
      거치지 않고 `QuizAttempt` 두 개를 완전히 같은 `submitted_at`으로
      직접 만들어 저장한 뒤, `get_latest_for_quiz`가 고른 시도가
      `list_for_quiz`의 1등 항목과 항상 일치하는지(그리고 둘 다 `id`가
      더 큰 쪽을 고르는지) 확인한다. `git stash`로 리포지토리 수정만
      되돌리면 이 테스트가 정확히 실패하는 것까지 확인했다(SQLite가
      명시적 정렬 없이는 삽입 순서로 반환해, 수정 전 코드는 `id`가 더
      작은 쪽을 "최신"으로 잘못 골랐다). 전체 389개 테스트 통과, 전체
      커버리지 99%(`quiz_attempt_repository.py` 100% 유지), mypy 클린.
      정렬 기준만 바뀐 순수 내부 수정이라 API 응답 형태나
      `docs/FRONTEND_INTEGRATION.md`에 영향이 없고, 마이그레이션도
      필요 없었다.

## 백로그 (101라운드)

- [x] 125. 범용 Ollama 프록시 `POST /api/v1/chat`만 `OllamaServiceError`를
      500(우리 서버 버그)으로 응답하던 문제 수정. `study_service.py`에는
      "`quiz_service`/`interview_practice_service`/`interview_review_service`
      는 전부 Ollama 호출 실패를 502(우리 서버가 아니라 업스트림 AI 엔진의
      문제)로 응답하는데, 이 서비스만 500으로 응답하고 있었다"는 이력이
      남긴 주석이 이미 있었다 - 그 이전 라운드가 서비스 계층의 4곳은
      전부 502로 통일했지만, 딱 하나 `chat.py`만은 서비스 계층을 거치지
      않고 라우트에서 직접 `OllamaServiceError`를 잡아 처리하는 구조라
      그 스윕에서 빠져 있었다(`routes/models.py`는 이미 502로 맞게
      돼 있는 것도 확인함). 같은 실패 원인인데 라우트마다 다른 상태
      코드가 나가면, 상태 코드로 분기하는 프론트가 이 엔드포인트의
      AI 엔진 장애를 "우리 서버 버그"로 잘못 분류하게 된다.
      `HTTPException(status_code=500, ...)`을
      `HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, ...)`로
      바꿨다. `tests/test_chat.py::test_chat_upstream_failure_returns_500`
      을 `test_chat_upstream_failure_returns_502`로 바꿔 새 기대값을
      고정했고, `git stash`로 라우트 수정만 되돌리면 이 테스트가
      정확히 실패하는 것까지 확인했다. 부수적으로
      `tests/test_error_format.py::test_ollama_service_error_returns_internal_error_code`
      도 status→code 매핑 검증이라 함께 걸렸는데(500→`internal_error`
      매핑을 확인하던 테스트가 이제 502→`bad_gateway`가 맞음), 이름과
      기대값을 `test_ollama_service_error_returns_bad_gateway_code`로
      갱신했다 - 이 엔드포인트는 "우리 서버 프로토타입용이라 신규 연동
      비추천"이라고만 문서화돼 있고 구체적인 실패 상태 코드는 원래
      `docs/FRONTEND_INTEGRATION.md`에 없어서 문서 갱신은 필요 없었다.
      전체 389개 테스트 통과, 전체 커버리지 99%(`routes/chat.py` 100%
      유지), mypy 클린. 마이그레이션은 필요 없었다.

## 백로그 (102라운드)

- [x] 126. `RefreshRequest.refresh_token`(`POST /auth/refresh`,
      `POST /auth/logout`가 공유 - 둘 다 로그인 없이 호출되는 인증 전
      경로)에만 길이 상한이 전혀 없던 문제 수정. 스키마 계층의 다른
      사용자 입력 필드는 전부 명시적 상한이 있다 - 비밀번호는
      `max_length=72`, 학습챗/면접복기 content는 `field_validator`로
      `max_prompt_length`/`max_review_content_length`를 검사, 제목/주제류는
      255자 등. 실제 발급되는 토큰(`core.tokens.generate_refresh_token`이
      `secrets.token_urlsafe(32)`로 만듦)은 43자 고정이라 실질적 위험은
      낮다(전체 요청 바디는 이미 `MaxBodySizeMiddleware`로 1MB 상한이
      있고, `hash_refresh_token`도 SHA-256이라 입력 크기와 무관하게
      저렴함) - 그래도 이 코드베이스 전체가 지켜온 "사용자 입력 필드는
      전부 명시적 상한을 둔다"는 검증 태도의 일관성이 깨진 곳이라 고쳤다.
      `Field(..., min_length=1, max_length=512)`로 여유 있는 안전장치를
      추가했다(95라운드의 RAG 후보 청크 상한처럼 "주 방어선이 아니라
      최후의 안전장치"로 넉넉하게 잡음). 회귀 테스트
      `test_refresh_rejects_token_over_max_length`/
      `test_logout_rejects_token_over_max_length`(513자를 보내면 두
      엔드포인트 모두 - 모르는 토큰이라 401이 아니라 - 스키마 검증에서
      바로 422로 거부되는지)를 추가했고, `git stash`로 스키마 수정만
      되돌리면 둘 다 정확히 실패하는 것까지 확인했다. 전체 391개 테스트
      통과, 전체 커버리지 99%(`schemas/auth.py` 100% 유지), mypy 클린.
      요청 바디 필드에 상한이 새로 생겼을 뿐 정상 범위의 기존 호출은
      전혀 영향받지 않는 순수 방어적 강화라 `docs/FRONTEND_INTEGRATION.md`
      갱신도, 마이그레이션도 필요 없었다.

## 백로그 (103라운드)

- [x] 127. `StudyMessageRepository.list_for_session`/`list_for_sessions`가
      `created_at`만으로 정렬해, 같은 세션에서 몇 ms 사이에 만들어지는
      user/assistant 메시지 쌍의 순서가 SQLite(`server_default=CURRENT_TIMESTAMP`,
      초 단위 정밀도)에서 실제로 흔들릴 수 있던 문제 수정. 같은 파일의
      `list_recent_for_session`은 정확히 이 문제(같은 요청 안에서 근접
      생성되는 메시지 쌍)를 주석으로 지적하며 `id`를 2차 정렬 기준으로
      쓰고 있었는데, 형제 메서드인 `list_for_session`/`list_for_sessions`
      는 그 수정에서 빠져 있었다 - 지금까지 완료한 id 2차 정렬 스윕은
      "페이지네이션 있는 목록"만 대상으로 했었고, 이 두 메서드는
      페이지네이션이 없어 그 스윕 범위 밖에 있었다. 이 순서는 실제로
      `GET /study/sessions/{id}`가 대화를 화면에 그대로 렌더링하는
      순서, `QuizService.create_quiz`(study_session_id 경로)가 메시지를
      이어붙여 퀴즈 생성 프롬프트를 만드는 순서, `export_service.py`가
      내보내는 JSON의 메시지 순서로 직접 쓰인다.

      처음엔 `list_for_session`/`list_for_sessions`에 그냥 `id`를 2차
      정렬 기준으로만 추가했는데, 훅으로 걸린 `test_stream_message_sends_deltas_then_done`
      이 바로 실패했다 - `StudyMessage.id`는 (다른 엔티티들과 마찬가지로)
      `uuid.uuid4()`로 만드는 완전히 무작위인 값이라, "동률을 결정론적으로
      깬다"는 건 보장해도 "생성 순서를 보존한다"는 보장은 전혀 없다.
      `QuizAttempt.submitted_at`처럼 "동률 중 아무거나 골라도 상관없는"
      경우엔 무작위 id 타이브레이크로 충분하지만, 대화 메시지는 순서
      자체가 의미(질문 다음에 답변)라 무작위 타이브레이크로는 부족했다 -
      실제로 고쳐보니, SQLite가 명시적 정렬 없이는 삽입 순서로 반환해주던
      "우연히 맞았던" 이전 동작보다 오히려 나빠져(assistant가 user보다
      먼저 나올 수 있음), 진짜 근본 수정이 필요했다. `QuizAttempt.submitted_at`
      이 겪었던 것과 똑같은 근본 원인이라, 똑같은 해법을 그대로 가져와
      `StudyMessage.created_at`도 DB의 `server_default=func.now()` 대신
      파이썬 쪽 마이크로초 정밀도 `default=utcnow_naive`로 바꿨다 - 이러면
      실제 동률이 사실상 안 일어나 자연스러운 시간순이 곧 인과관계상
      올바른 순서가 된다. 그 위에 `id` 2차(`list_for_session`) /
      3차(`list_for_sessions`, `session_id`/`created_at` 다음) 정렬은
      순수 결정론 보장용 안전장치로 남겨뒀다(진짜 마이크로초 동률이
      일어나는 극히 드문 경우에만 관여하므로 더 이상 위험 요소가 아님).
      `submitted_at`과 마찬가지로 컬럼 타입은 그대로고 파이썬 쪽 기본값만
      바뀐 거라 마이그레이션은 필요 없었다(migrations/versions의 원본
      CREATE TABLE에 남아있는 DB 레벨 `server_default`는 ORM이 항상 값을
      명시적으로 채워 넣으므로 그냥 안 쓰이게 됨 - `submitted_at` 때와
      동일).

      새 테스트 파일 `tests/test_study_message_ordering.py`에 3개 추가:
      `test_create_gives_back_to_back_messages_distinct_microsecond_timestamps`
      (연달아 만든 두 메시지의 `created_at`이 실제로 달라지는지),
      `test_list_for_session_preserves_creation_order_across_many_back_to_back_messages`
      (6개를 연달아 만들어도 `list_for_session`이 생성 순서를 그대로
      보존하는지), `test_list_for_session_breaks_genuine_created_at_ties_deterministically_by_id`
      (94라운드 기법대로 `create()`를 거치지 않고 완전히 같은 `created_at`
      을 강제로 만들어, id 오름차순 - `list_recent_for_session`과 같은
      상대 순서 - 로 결정론적으로 정렬되는지). `git stash`로 리포지토리/
      모델 수정을 모두 되돌리면 처음 두 테스트가 정확히 실패하는 것까지
      확인했다(세 번째는 우연히 통과 - id 타이브레이크만으로도 "무작위지만
      일관된" 순서는 나오기 때문에, 이 테스트 하나만으론 순서의 의미
      자체가 틀렸다는 걸 못 잡는다는 걸 보여주는 사례이기도 하다).
      전체 394개 테스트 통과, 전체 커버리지 99%(`db/models/study_message.py`/
      `repositories/study_message_repository.py` 모두 100%), mypy 클린.
      응답 형태는 그대로고 내부 정렬/타임스탬프 정밀도만 바뀐 변경이라
      `docs/FRONTEND_INTEGRATION.md` 갱신은 필요 없었다.

## 백로그 (104라운드)

- [x] 128. `knowledge_chunks` 테이블에 `(user_id, embedding_model, created_at)`
      복합 인덱스 추가. `KnowledgeChunkRepository.list_for_user`(학습챗/
      면접연습 매 턴마다 RAG 검색 시 호출되는 핫 패스)가 정확히 이 세
      컬럼으로 필터(`user_id`, `embedding_model`)하고 정렬(`created_at`)
      하는데, 지금까지는 `user_id` 단일 컬럼 인덱스만 있었다. 이 테이블은
      만료/정리 로직이 없어 계정이 오래될수록 계속 쌓이기만 한다는 걸
      리포지토리 자체 주석도 이미 인지하고 있던 상태(95라운드에서
      `rag_max_candidate_chunks`라는 안전장치를 넣은 이유이기도 함) - 단일
      컬럼 인덱스만으로는 `embedding_model` 필터링과 정렬을 인덱스 스캔
      이후에 처리해야 해서, 계정이 커질수록 이 조회부터 먼저 느려질
      후보였다. 개인/소규모 사용 스케일에서는 지금 당장 체감될 문제는
      아니지만, 인덱스 하나 추가하는 값싼 사전 대응이라 지금 처리했다.
      `KnowledgeChunk` 모델에 `Index("ix_knowledge_chunks_user_id_embedding_model_created_at",
      "user_id", "embedding_model", "created_at")`를 `__table_args__`로
      추가하고, 로컬 Postgres 16 클러스터에 연결해 `alembic revision
      --autogenerate`로 마이그레이션을 생성했다 - 자동 생성된 내용이
      의도한 인덱스 추가 하나뿐인지 확인했고, `alembic upgrade head` →
      `downgrade -1` → `upgrade head`로 업/다운그레이드 왕복이 깨끗하게
      되는 것도 확인했다. 적용 후 다시 `--autogenerate`를 돌려 빈
      마이그레이션(변경사항 없음)이 나오는지로 모델과 실제 스키마 사이에
      드리프트가 없는지도 검증했다(빈 마이그레이션 파일은 확인 후 삭제).
      인덱스만 추가하는 순수 성능 변경이라 리포지토리/서비스/라우트
      코드는 건드리지 않았고, 응답 형태에도 전혀 영향이 없어 회귀
      테스트는 기존 RAG 관련 테스트들이 여전히 통과하는 것으로 충분하다고
      판단했다(쿼리 결과 자체는 안 바뀌고 실행 계획만 바뀌는 변경이라
      SQLite 테스트 DB로는 인덱스 사용 여부 자체를 검증할 수 없다 -
      Postgres에서 마이그레이션 적용/드리프트 없음까지 확인한 것으로
      갈음). 전체 394개 테스트 통과, 전체 커버리지 99%(`db/models/knowledge_chunk.py`/
      `repositories/knowledge_chunk_repository.py` 모두 100% 유지), mypy
      클린. 순수 인덱스 추가라 `docs/FRONTEND_INTEGRATION.md` 갱신은
      필요 없었다.

## 백로그 (105라운드)

- [x] 129. 학습챗/면접연습 세션을 지울 때 RAG 색인을 지우는 게 메시지/턴
      개수만큼 개별 `DELETE`+`commit`을 반복하던 N+1 쓰기 패턴 수정.
      `StudyService.delete_session`/`InterviewPracticeService.delete_session`
      은 (98라운드에서 "세션을 지워도 RAG 색인이 안 지워지던" 정합성
      버그를 고치면서 생긴 구조 그대로) 세션에 속한 메시지/턴 id를 먼저
      모은 뒤, 그 목록을 파이썬 `for` 루프로 돌며 `RagService.forget_content`
      를 하나씩 호출했다 - `forget_content`는 호출마다 `DELETE`와
      `session.commit()`을 각각 하나씩 실행하므로, 메시지 100개가 쌓인
      학습챗 세션을 지우면 그것만으로 DB 왕복이 100번 생기는 구조였다.
      `max_chat_history_messages`(AI에게 넘길 최근 히스토리 개수)는
      세션에 저장 가능한 총 메시지 수 자체는 전혀 제한하지 않아, 오래
      쓴 세션일수록 이 문제가 커진다. `KnowledgeChunkRepository`에
      `delete_for_sources(source_type, source_ids: list[uuid.UUID])`
      배치 버전(`IN` 절)을 추가하고, `RagService`에 그걸 감싸는
      `forget_content_bulk`(빈 리스트면 DB 호출 없이 바로 반환)를
      추가했다. 두 서비스의 `delete_session` 모두 반복 호출 대신 id
      리스트를 모아 한 번만 호출하도록 바꿨다 - 끝 결과(색인 전부 삭제)
      는 그대로라 순수 성능 리팩터링이고, 서비스 계약/응답 형태는
      전혀 안 바뀌었다.

      끝 결과가 그대로인 리팩터링이라, 회귀 테스트를 "결과가 같은지"로만
      짜면 `git stash`로 되돌려도 통과해버려 아무것도 증명 못 한다는 걸
      먼저 확인했다(실제로 시도해봄) - 92/93라운드가 N+1 SELECT를 고칠 때
      썼던 것과 같은 기법(`before_cursor_execute` 이벤트로 실제 실행되는
      SQL 문 개수를 직접 셈)을 DELETE 문에 적용해, `knowledge_chunks`
      DELETE가 메시지/턴 개수와 무관하게 정확히 1번만(IN 절로 묶여서)
      나가는지 확인하는 방식으로 바꿨다. `git stash`로 리포지토리/서비스
      수정을 되돌리면 실제로 메시지 2개(대화 2번=청크 4개)에 DELETE가
      1번이 아니라 4번, 턴 2개엔 3번(첫 질문 색인 포함) 나가는 것까지
      직접 확인했다. 이 김에 `InterviewPracticeService.delete_session`
      쪽엔 RAG 정리를 검증하는 테스트가 아예 없었다는 것도 발견해서(기존
      `test_delete_session_with_answered_turns`는 204만 확인) 새 파일
      `tests/test_interview_practice_session_delete_rag_cleanup.py`를
      `test_study_session_delete_rag_cleanup.py`와 대칭으로 만들었다.
      `delete_for_sources`에 빈 리스트를 주는 안전장치(다른 `list_for_*`
      류와 같은 관용구)도 직접 호출해 no-op임을 확인하는 테스트를
      추가했다(커버리지에서 그 분기가 안 걸린 걸 보고 알아챔 -
      `forget_content_bulk`가 이미 빈 리스트를 걸러줘 리포지토리 메서드
      자체를 빈 입력으로 직접 부르는 경로가 없었다). 전체 398개 테스트
      통과, 전체 커버리지 99%(`repositories/knowledge_chunk_repository.py`/
      `services/rag_service.py`/`services/study_service.py`/
      `services/interview_practice_service.py` 모두 100%), mypy 클린.
      응답 형태/타이밍(색인 삭제가 언제 반영되는지)이 전혀 안 바뀐 내부
      성능 개선이라 `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도
      필요 없었다.

## 백로그 (106라운드)

- [x] 130. 면접복기 스트리밍 WebSocket(`POST /interview/reviews/stream`)이
      pydantic `ValidationError`를 `str(exc)`로 그대로 클라이언트에 흘려보내,
      검증에 실패한 필드의 원본 입력값이 에러 메시지에 그대로 노출되던 문제
      수정. `app/core/errors.py`의 `validation_exception_handler`는 정확히
      이 이유("password/current_password/refresh_token처럼 민감한 필드가
      검증 실패하면 원본 값이 그대로 응답에 실려서 devtools 히스토리/로깅
      도구에 남을 수 있다")로 REST 422 응답에서 `input` 필드를 이미 제거하고
      있었는데, 이 WS 라우트는 FastAPI의 자동 검증 경로를 안 타고
      `InterviewReviewCreateRequest.model_validate()`를 직접 호출해서 그
      sanitization을 전혀 거치지 않았다. pydantic v2의 `ValidationError.__str__()`
      은 실패한 필드의 `input_value`를 기본적으로 포함하므로(길면 가운데를
      잘라서 보여주지만 앞부분은 그대로 남음), `content`가
      `max_review_content_length`를 넘으면 사용자가 입력한 면접 복기 내용
      앞부분이 에러 메시지에 그대로 echo됐다 - 학습챗 WS 라우트(`study.py`)
      는 pydantic 모델 검증을 안 쓰고 수동으로 필드를 확인해서 이 문제가
      없다는 것도 확인함(같은 라우트 그룹에서 이 경로만 취약).
      `app/core/errors.py`에서 `input` 필드 제거 로직을 `sanitize_pydantic_errors()`
      공용 헬퍼로 뽑아 `validation_exception_handler`가 그대로 재사용하도록
      바꾸고, WS 라우트도 이 헬퍼로 원본 값을 뺀 뒤 필드 위치/메시지만 이어
      붙인 문자열을 `detail`로 보내도록 고쳤다.

      회귀 테스트를 처음 작성할 때 실수를 하나 했다 - 민감한 content 전체
      문자열이 에러 메시지에 없는지 확인하려 했는데, pydantic이 긴
      `input_value`는 가운데를 `...`로 잘라서 보여준다는 걸 몰라서, 고치기
      전 코드로 `git stash` 검증을 해보니 (전체 문자열은 어차피 안 남아서)
      수정 전 코드에서도 테스트가 통과해버렸다 - 아무것도 증명 못 하는
      테스트였던 것. 잘려도 살아남는 맨 앞 마커 문자열(`SECRETMARKER98765`
      + 반복 문자)로 바꿔서 다시 확인하니, 수정 전엔 실제로 이 마커가 에러
      메시지에 그대로 남아 있어 테스트가 정확히 실패하는 것을 확인했다.
      `test_stream_create_review_validation_error_does_not_leak_raw_input_value`
      로 추가. 전체 399개 테스트 통과, 전체 커버리지 99%(`core/errors.py`/
      `routes/interview_review.py` 모두 100%), mypy 클린. 에러 메시지
      형태가 조금 달라졌을 뿐(원본 입력값이 빠지고 필드 위치/메시지만
      남음) 프로토콜/스키마는 그대로라 `docs/FRONTEND_INTEGRATION.md`
      갱신도, 마이그레이션도 필요 없었다.

## 백로그 (107라운드)

- [x] 131. `RagService.index_content`/`forget_content`/`forget_content_bulk`
      가 `OllamaServiceError`(임베딩 API 실패)만 잡아서 조용히 넘어가도록
      돼 있어, 그 범위 밖의 예상 못한 예외(예: `_chunks.create()`의
      `flush()`나 `session.commit()`에서 나는 DB 레벨 오류 - 커넥션 드롭,
      제약 위반 등)는 그대로 위로 전파되던 문제 수정. 이 세 메서드는
      전부 "본 리소스(학습챗 메시지/퀴즈/면접복기/면접연습 턴)가 이미
      커밋(생성 시엔 색인, 삭제 시엔 색인 정리)된 뒤" 마지막 단계로만
      호출된다 - `study_service.py`/`quiz_service.py`/
      `interview_review_service.py`/`interview_practice_service.py`의
      모든 호출부를 확인해, 이 뒤에 이어지는 코드가 세션에 의존하지
      않는다는 것도 확인했다(전부 `return` 직전 마지막 호출). 그런데
      정작 각 서비스 docstring엔 "색인은 부가 기능이라 본 기능 흐름을
      막으면 안 된다"고 명시돼 있으면서, 좁은 예외 타입(`OllamaServiceError`)
      만 잡아 그 의도가 실제로는 지켜지지 않는 구멍이 있었다 - 이 좁은
      틈에서 DB 오류가 나면, 이미 성공한 요청(리소스는 실제로
      생성/삭제됨)이 클라이언트에는 500으로 보여, 특히 멱등성 가드가
      없는 `create_quiz`/`create_review` 같은 엔드포인트는 재시도 시
      중복 리소스가 쌓일 위험까지 있었다. 세 메서드 모두 바깥쪽에
      `try/except Exception`을 씌워(임베딩 호출용 안쪽 `except
      OllamaServiceError`는 그대로 남기고, 그 바깥의 `_chunks` 조작+
      `commit()` 구간 전체를 감쌈) `logger.exception`으로 남긴 뒤
      `session.rollback()`으로 세션을 깨끗한 상태로 되돌린다(이 시점
      이후로 세션을 계속 쓰는 곳이 없다는 걸 위에서 이미 확인했지만,
      FastAPI의 `get_db()` yield 의존성이 요청 끝에서 세션을 재사용할
      가능성에 대비한 안전장치).

      새 파일 `tests/test_rag_service_best_effort.py`에 회귀 테스트 3개
      추가 - `_BrokenChunkRepository`(모든 메서드가 `OllamaServiceError`가
      아닌 `RuntimeError`를 던지도록 흉내낸 가짜 리포지토리)를
      `RagService._chunks`에 직접 주입해, `index_content`/`forget_content`/
      `forget_content_bulk` 호출이 예외를 밖으로 새어나가게 하지 않는지,
      그리고 그 뒤 같은 세션으로 다른 작업(새 게스트 유저 생성+커밋)을
      해도 정상 동작하는지(rollback이 실제로 세션을 깨끗한 상태로
      되돌렸는지) 확인한다. `git stash`로 서비스 수정만 되돌리면 세
      테스트 모두 `RuntimeError`가 그대로 전파되며 정확히 실패하는 것까지
      확인했다. 전체 402개 테스트 통과, 전체 커버리지 99%(`services/rag_service.py`
      100% 유지), mypy 클린. 예외 처리 범위만 넓어졌을 뿐 정상 경로의
      동작/응답 형태는 전혀 안 바뀐 변경이라 `docs/FRONTEND_INTEGRATION.md`
      갱신도, 마이그레이션도 필요 없었다.

## 백로그 (108라운드)

- [x] 132. AI가 생성한 퀴즈 데이터에 대한 신뢰 경계 검증 공백 두 가지 수정
      (`QuizService._generate_quiz`). `question_count`는 사용자 요청 시점에만
      `max_quiz_question_count`(기본 20)로 제한되고, 모델에게는 프롬프트로
      "이 개수만큼 만들어달라"고 부탁만 할 뿐 구조적으로 강제되지 않는다 -
      실제로 모델이 요청보다 훨씬 많은 문항을 뱉어도 지금까지는 전혀 걸러지지
      않고 그대로 개별 INSERT로 전부 저장됐다(응답 payload 비대화, DB 행
      폭증, 순차 INSERT 지연으로 이어질 수 있음). 더 심각한 건 채점
      로직(`submit_answers`)이 보기 인덱스가 아니라 **문자열 값**으로 정답을
      비교한다는 점이다 - `_generate_quiz`는 `correct_answer in choices`만
      확인할 뿐 "정확히 한 번만 나타나는지"는 검증하지 않아서, 모델이 같은
      보기 문자열을 중복 생성하면(예: `["파리", "런던", "파리", "베를린"]`,
      correct_answer="파리") 실제로는 오답인 인덱스를 골라도 값 비교상
      정답으로 채점되는 정합성 문제로 이어질 수 있었다. `Settings`에
      `max_quiz_choice_count: int = 8`(문항당 보기 개수 상한 - 기존
      `max_quiz_question_count`와 같은 신뢰 경계 안전장치 성격)을 새로
      추가하고, `_generate_quiz`의 검증 단계(기존 `correct_answer in choices`
      체크 자리)에 "문항 수가 상한 이하", "보기 개수가 상한 이하",
      "보기에 중복이 없음"(중복이 없고 `correct_answer`가 `choices` 안에
      있다는 기존 체크가 함께 있으면, 정답 문자열이 정확히 한 번만 나타난다는
      것도 자동으로 보장됨) 세 조건을 추가했다 - 실패하면 기존 재시도 경로
      (`_MAX_QUIZ_GENERATION_ATTEMPTS`)를 그대로 타고, 재시도까지 실패하면
      기존과 동일하게 502로 끝난다. `tests/test_quiz.py`에 두 가짜 Ollama
      서비스(`TooManyQuestionsOllamaService`: 25문항 생성,
      `DuplicateChoicesOllamaService`: 같은 보기 문자열 중복 생성)와 그걸
      쓰는 회귀 테스트 2개를 추가했고, `git stash`로 서비스/설정 수정만
      되돌리면 둘 다 (검증을 통과해 실제로 퀴즈 생성이 진행되면서 이 코드
      경로와 무관한 다른 예외로) 정확히 실패하는 것까지 확인했다. 전체
      404개 테스트 통과, 전체 커버리지 99%(`services/quiz_service.py`/
      `core/config.py` 모두 100%), mypy 클린. AI가 실제로 상한을 넘겨
      생성하는 극히 드문 경우에만 영향을 주는(정상 범위 응답은 그대로
      통과) 순수 방어적 강화라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (109라운드)

- [x] 133. 모든 응답에 `Cache-Control: no-store` 헤더 추가
      (`SecurityHeadersMiddleware`). `X-Content-Type-Options`/`X-Frame-Options`/
      `Referrer-Policy`/`Strict-Transport-Security`는 이미 챙기고 있었는데
      `Cache-Control`은 코드베이스 전체에 한 번도 등장하지 않았다. 이 API는
      Bearer 토큰 인증이라 브라우저 기본 캐시 정책이 어느 정도 안전망 역할을
      하지만, `GET /export/me`처럼 계정 전체 이력(학습챗 내용, 퀴즈 정답,
      면접 복기 원문)을 한 번에 반환하는 엔드포인트를 포함해 모든 GET
      응답에 명시적인 `no-store`가 없다는 건, 공유 컴퓨터의 브라우저 디스크
      캐시나 back-forward cache, 혹은 향후 Caddy 앞단에 캐싱 프록시/CDN이
      추가될 경우의 사고 가능성을 열어둔다 - 심층 방어(defense-in-depth)
      성격의 공백이었다. 정적 자산을 서빙하지 않는 순수 API 서버라 모든
      응답에 일괄 적용해도 부작용이 없고(`/docs`/`/redoc`/`/openapi.json`도
      이미 프로덕션에서 비활성화돼 있어 예외 처리가 따로 필요 없음),
      `SecurityHeadersMiddleware._HEADERS` 튜플에 한 줄 추가하는 것으로
      끝나는 값싼 수정이었다. `test_security_headers_present`에 헤더
      확인 한 줄을 추가했고, `git stash`로 미들웨어 수정만 되돌리면
      정확히 실패하는 것까지 확인했다. 전체 404개 테스트 통과, 전체
      커버리지 99%(`core/middleware.py` 100% 유지), mypy 클린. 응답
      헤더 하나가 늘었을 뿐 바디/상태 코드는 전혀 안 바뀌는 변경이라
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (110라운드)

- [x] 134. 면접 복기 `interview_date`에 도메인 상 말이 안 되는 미래 날짜가
      그대로 허용되던 문제 수정. `company`/`position`/`content`는 전부
      길이 상한이 있는데(93~97라운드 스윕 대상) `interview_date`만 순수
      `date` 타입 검증뿐 아무 도메인 검증이 없었다 - "면접 복기"는 이미
      치른 면접을 되짚는 기능인데도 100년 후 미래 날짜가 그대로 저장될 수
      있었고, 정렬 기준으로도 쓰이는 값이라(107라운드 근처에서 이미
      `interview_date` DESC 정렬의 동률 처리를 다룬 적 있음) 터무니없는
      값이 섞이면 정렬 UX가 깨지고 export/통계에도 이상치로 나타날 수
      있었다. "얼마나 먼 과거까지 허용할지"는 제품 판단이 필요해 하한은
      일부러 두지 않고(오래된 면접을 뒤늦게 기록하는 경우가 실제로 있을
      수 있음), 명백히 모순인 미래 날짜만 막는 최소선으로 골랐다.
      `InterviewReviewCreateRequest`/`InterviewReviewUpdateRequest` 둘 다에
      `field_validator`를 추가해 `interview_date`가 `utcnow_naive().date()`
      (오늘)보다 미래면 거부하고, 오늘 날짜 자체는 허용한다(당일 면접을
      바로 복기하는 것도 정상 케이스라). 회귀 테스트
      `test_create_review_rejects_future_interview_date`/
      `test_update_review_rejects_future_interview_date`(내일 날짜로
      422 확인)와 `test_create_review_accepts_todays_interview_date`(오늘
      날짜는 거부되면 안 됨)를 추가했고, `git stash`로 스키마 수정만
      되돌리면 미래 날짜 거부 테스트 둘 다 정확히 실패하는 것까지
      확인했다. 검증 과정에서 새로 추가한 `InterviewReviewUpdateRequest`
      쪽 None 분기(값을 아예 안 보내거나 명시적으로 `null`을 보낸 경우)가
      커버리지에서 안 걸린 걸 보고, 일부 클라이언트는 "안 바꾼 필드"도
      명시적으로 `null`로 보낼 수 있다는 걸 확인해
      `test_update_review_with_explicit_null_interview_date_leaves_it_unchanged`
      (명시적 `null`이 필드 생략과 동일하게 기존 값을 그대로 유지하는지)
      를 추가로 채워 넣었다. `docs/FRONTEND_INTEGRATION.md`의 면접 복기
      절에 이 새 검증 규칙을 문서화했다(생성/수정 응답 코드에 영향을 주는
      새 제약이라 92라운드 이후 확립된 "사용자 관찰 가능한 계약 변경은
      문서화한다" 관례를 따름). 전체 408개 테스트 통과, 전체 커버리지
      99%(`schemas/interview_review.py`의 유일한 미커버 라인은 106라운드
      부터 있던 이 라운드와 무관한 기존 분기), mypy 클린. 기존 정상
      범위(과거/오늘 날짜) 요청은 전혀 영향받지 않는 순수 방어적 강화라
      마이그레이션은 필요 없었다.

## 백로그 (111라운드)

- [x] 135. RAG 백필 cron(`backfill_unindexed_content`)의 "미색인" 조회
      4개(학습챗 메시지/면접 복기/퀴즈 소스/면접연습 턴) 전부에 처리 건수
      상한이 없던 문제 수정. 이 job은 각 서비스가 생성 시점에 이미 동기로
      색인하므로 평상시엔 임베딩 API 일시 실패 같은 극소수만 찾아내
      무해하지만(LEFT JOIN으로 걸러내는 방식으로 이미 회귀 방지된 상태),
      만약 Ollama 임베딩 엔드포인트가 며칠 연속 다운되면(운영 환경이 단일
      오라클 서버 Ollama에 의존) 그 기간 쌓인 미색인 행 전체가 복구 후
      첫 실행에 한꺼번에 몰린다 - 이 함수가 그 행 전체를 한 번에
      파이썬으로 읽어와 **순차** `index_content()` 호출(임베딩 API 왕복
      각각 1회)을 돌리는 동안, `get_db()`가 물어준 DB 커넥션 하나를
      비정상적으로 오래 점유하게 된다(99라운드가 WebSocket 경로에서 다룬
      것과 같은 종류의 풀 점유 리스크가 스케줄러 경로에도 있던 셈 - 딱
      "장애 복구 직후"라는 가장 필요한 순간에 악화되는 성격이라 평소엔
      안 드러난다). `Settings.rag_backfill_batch_size: int = 500`(카테고리당
      한 번의 실행에서 재시도하는 최대 건수)을 추가하고, 4개 쿼리 전부에
      `.limit(settings.rag_backfill_batch_size)`를 걸었다 - `backfill_unindexed_content`
      가 이제 `settings`를 명시적 매개변수로 받도록 시그니처를 바꿨다(스케줄러
      엔트리포인트 `run_scheduled_rag_backfill`은 이미 `settings`를
      들고 있어 그대로 넘기기만 하면 됨). 상한에 걸려 처리량이 상한과
      같아지면(=더 남아있을 가능성) `_log_if_batch_capped` 헬퍼로 경고
      로그를 남긴다 - 며칠 연속 이 로그가 찍히면 백로그가 쌓이고 있다는
      운영 신호가 된다. 상한을 못 채운 나머지는 멱등적인 LEFT JOIN
      쿼리라 다음 실행에서 자동으로 다시 잡히므로 데이터 유실은 없다.
      회귀 테스트 `test_backfill_unindexed_content_caps_at_batch_size_and_warns`
      (`RAG_BACKFILL_BATCH_SIZE=2`로 낮추고 미색인 메시지 3개를 만들어,
      실제로 2개만 처리되고 경고 로그가 남는지, 그리고 진짜로 2개만
      `knowledge_chunks`에 색인되는지)를 추가했다. `git stash`로 서비스/
      설정 수정을 되돌리면 시그니처 자체가 없어져 정확히 실패하는 것까지
      확인했다(순수 성능/안전장치 변경이라 end-state 비교만으로는 fix
      전후를 구분할 수 없는 성격 - 129라운드와 같은 종류의 검증 한계).
      함수 시그니처가 바뀌어 기존 리포지토리 테스트 8곳의 호출부도 함께
      갱신했다. 전체 409개 테스트 통과, 전체 커버리지 99%(`services/rag_backfill_service.py`/
      `core/config.py` 모두 100%), mypy 클린. 스케줄러 내부 동작만 바뀐
      변경이라 API 응답 형태에 영향이 없어 `docs/FRONTEND_INTEGRATION.md`
      갱신은 필요 없었고, 컬럼/테이블 변경이 없어 마이그레이션도 필요
      없었다.

## 백로그 (112라운드)

- [x] 136. 퀴즈 생성 시 AI가 만든 문항을 하나씩 개별 `flush()`로 저장하던 것을
      배치 저장으로 바꿈. `create_quiz`가 `for index, question in
      enumerate(generated.questions): await self._questions.create(...)`로
      루프를 돌았는데, `QuizQuestionRepository.create()`가 호출마다
      `session.add()` 직후 `flush()`(=DB 왕복)를 했다 - 문항 수(최대
      `max_quiz_question_count`, 기본 20)만큼 개별 INSERT 왕복이 생기는
      구조였다. 이미 몇 초짜리 Ollama 호출을 거친 뒤에 이어지는 구간이라
      사용자 체감 지연에 그대로 얹히는 비용이었다. `QuizQuestionRepository`
      에 `create_many(quiz_id, questions: list[tuple[...]])` 배치 메서드를
      추가해(`session.add_all()` + `flush()` 한 번), `create_quiz`가 이걸
      쓰도록 바꿨다 - 저장된 문항 객체를 이후에 안 쓰는 이 호출부에서만
      안전하게 쓸 수 있는 형태라 반환값은 없앴다(기존 반환값도 안
      쓰이고 있었음). 129라운드(세션 삭제 시 RAG 정리 배치화)와 같은
      종류의 순수 성능 리팩터링이라 끝 결과(저장되는 문항/내용은 동일)가
      그대로라, 회귀 테스트도 같은 기법(`before_cursor_execute` 이벤트로
      실제 실행되는 SQL 문 개수를 직접 셈)을 썼다.
      `test_create_quiz_issues_a_single_batch_insert_for_questions`이
      문항 2개(`SAMPLE_QUIZ_JSON`)로 퀴즈를 만들어도 `quiz_questions`
      INSERT 문이 정확히 1번만(executemany 배치 포함) 나가는지, 그리고
      `order_index`가 리스트 순서 그대로 0, 1로 정확히 부여되는지 확인한다.
      `git stash`로 리포지토리/서비스 수정만 되돌리면 실제로 INSERT가
      2번(문항 개수만큼) 나가는 것까지 확인했다. 전체 410개 테스트
      통과, 전체 커버리지 99%(`repositories/quiz_repository.py`/
      `services/quiz_service.py` 모두 100%), mypy 클린. 저장되는
      데이터/응답 형태는 전혀 안 바뀐 순수 내부 성능 개선이라
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (113라운드)

- [x] 137. `docker-compose.yml`이 `ENVIRONMENT`를 컨테이너에 전달하지 않아,
      실제 배포에서 `.env`에 `ENVIRONMENT=production`을 정확히 적어도
      Swagger/ReDoc/OpenAPI가 계속 공개로 열려 있던 문제 수정(73/74라운드가
      막으려던 것과 같은 결과를 인프라 경로로 재현하고 있었음). `app/main.py`
      는 `settings.environment == "production"`일 때만 `/docs`/`/redoc`/
      `/openapi.json`을 끄는데, `.dockerignore`가 `.env`/`.env.*`를 빌드
      컨텍스트에서 명시적으로 제외해(이미지 안에 `.env` 파일 자체가 없음)
      컨테이너는 오직 `docker-compose.yml`의 `environment:` 목록에 있는
      변수만 볼 수 있다 - 그런데 그 목록(`DATABASE_URL`부터 `REDIS_URL`까지
      11개)에 `ENVIRONMENT`가 아예 빠져 있어서, 운영자가 `.env`를 아무리
      정확히 채워도 실제 컨테이너에는 전달되지 않고 `Settings`의 기본값
      ("development")으로 조용히 fallback됐다 - 진짜 공개 도메인(Let's
      Encrypt 인증서까지 발급된)으로 서빙되는 배포에서 문서 엔드포인트가
      인터넷에 그대로 노출되는 상태였던 것. `JWT_SECRET_KEY`/`DOMAIN`/
      `GRAFANA_ADMIN_PASSWORD`와 같은 방식으로 `ENVIRONMENT=${ENVIRONMENT:?ENVIRONMENT
      must be set (development or production)}`(필수값 - 안 채워졌으면
      시작 시 바로 실패)를 추가했다. 같은 구조로(문서화는 됐지만 실제
      전달은 안 되는) 누락돼 있던 `LOG_LEVEL`도 `${LOG_LEVEL:-INFO}`로
      같이 채워 넣었다(이쪽은 보안 이슈가 아니라 운영 편의성 문제라
      기본값 방식으로 처리 - 안 채워져도 안전한 기본값이 이미 있음).
      `Dockerfile`의 uvicorn 플래그 회귀를 텍스트로 직접 검증하는
      `tests/test_dockerfile.py`와 같은 패턴으로 새 파일
      `tests/test_docker_compose.py`를 만들어
      `test_haruhan_backend_receives_environment_variable`/
      `test_haruhan_backend_receives_log_level_variable`을 추가했다 -
      `git stash`로 `docker-compose.yml` 수정만 되돌리면 둘 다 정확히
      실패하는 것까지 확인했다. 겸사겸사 `AuthService.create_guest_session`
      의 "이후 실제 계정으로 전환하는 기능은 아직 없다"는 오래전에
      틀려진 주석(2라운드에서 `UserService.upgrade_guest()`/
      `POST /users/me/upgrade`가 이미 구현됨)도 같이 고쳤다 - 이 자동화
      루프 자체가 코드베이스의 주석/문서를 근거로 다음 라운드를 판단하는
      구조라, stale 주석이 향후 라운드의 판단을 잘못된 방향으로 이끌
      위험이 있다고 판단해 별도 라운드로 쪼개지 않고 함께 처리했다.
      전체 412개 테스트 통과, 전체 커버리지 99%(`docker-compose.yml`은
      애플리케이션 커버리지 대상이 아니라 텍스트 검증 테스트로 별도
      확인), mypy 클린. 애플리케이션 코드/API 응답 형태는 전혀 안
      바뀐 순수 배포 설정 수정이라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (114라운드)

- [x] 138. `Caddyfile`이 `/metrics`를 경로 제한 없이 그대로 프록시해, 공개
      도메인을 통해 누구나 인터넷에서 접근 가능했던 문제 수정.
      `app/api/v1/routes/metrics.py`의 `/metrics`는 "Prometheus가
      스크레이프할 엔드포인트... 인증 없이 노출한다(Prometheus 표준
      관례)"는 의도적 설계지만, 이 관례는 Prometheus가 내부 네트워크로
      직접 접근한다는 전제다 - 실제로 `monitoring/prometheus.yml`은
      `targets: ["haruhan-backend:8000"]`으로 `haruhan-net` 내부 docker
      네트워크를 통해 이 Caddy를 아예 거치지 않고 직접 스크레이프한다.
      그런데 `Caddyfile`은 경로 매칭 없이 `{$DOMAIN}` 전체를
      `reverse_proxy haruhan-backend:8000`으로 그대로 넘겨서, `/metrics`
      도 공개 도메인을 통해 접근 가능한 상태였다 - Prometheus가 이미
      내부망으로 스크레이프하고 있어 Caddy를 통한 공개 노출은 애초에
      아무 기능적 이유 없이 존재하는 구멍이었다. 노출되는 지표
      (`haruhan_user_signups_total`/`haruhan_guest_conversions_total`/
      `haruhan_quiz_created_total` 같은 비즈니스 카운터, 라우트별 요청
      수/응답시간)에 PII는 없지만 가입자 수·게스트 전환율·엔드포인트별
      실시간 트래픽 패턴이 누구에게나 공개되는 건 의도치 않은 정보
      노출이다. `handle /metrics { respond 404 }`를 나머지 경로를 처리하는
      `handle { reverse_proxy ... }`보다 앞에 둬서(Caddy의 `handle`은
      순서대로 먼저 매칭되는 블록만 적용되고 서로 배타적임) `/metrics`만
      막고 나머지는 그대로 프록시되게 했다. 로컬에 `caddy` 바이너리가
      없어(이 환경엔 Docker 데몬도 안 떠 있어 `caddy:2-alpine` 이미지도
      못 씀) `apt-get download caddy` + `dpkg-deb -x`로 .deb 패키지에서
      바이너리만 뽑아내 실제 Caddy 2.6.2로 직접 검증했다 - `caddy validate`
      로 문법이 유효한지 확인한 뒤, 스텁 백엔드(파이썬 `http.server`)를
      띄우고 실제 Caddy 프로세스를 로컬 포트로 구동해 `curl`로
      `/metrics`는 정확히 404, `/health`/`/api/v1/study/sessions`는
      그대로 백엔드까지 프록시되는 것을 라이브로 확인했다.
      `tests/test_caddyfile.py`에 `test_caddyfile_blocks_public_access_to_metrics`
      (`/metrics`와 `respond 404`가 파일에 있는지)를 추가했고, `git stash`
      로 `Caddyfile` 수정만 되돌리면 정확히 실패하는 것까지 확인했다.
      전체 413개 테스트 통과, 전체 커버리지 99%(`Caddyfile`은 애플리케이션
      커버리지 대상이 아니라 텍스트 검증 테스트 + 위 라이브 검증으로
      별도 확인), mypy 클린. 애플리케이션 코드는 전혀 안 건드린 순수
      배포 설정 수정이라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (115라운드)

- [x] 139. 104라운드가 추가한 `knowledge_chunks` 복합 인덱스 마이그레이션
      (`f8c776ddf837`)이 `CREATE INDEX`(비-concurrent)를 써서, 실제
      배포 시 이 테이블에 대한 쓰기를 인덱스 빌드가 끝날 때까지 막는
      락을 잡던 문제 수정. `knowledge_chunks`는 학습챗 메시지/면접
      복기/퀴즈 소스/면접연습 답변마다 계속 쌓이는 RAG 색인 테이블이라
      서비스가 커질수록 테이블도 커지는데, `migrations/env.py`는 모든
      마이그레이션을 트랜잭션 안에서 실행하고(`context.begin_transaction()`),
      비-concurrent `CREATE INDEX`는 그 트랜잭션이 인덱스 빌드가 끝날
      때까지 테이블 쓰기(INSERT/UPDATE/DELETE)를 막는 락을 들고 있는다 -
      이 마이그레이션을 그대로 프로덕션에 적용하면 배포 순간
      `RagService.index_content()`가 하는 쓰기가 전부 멈추는 다운타임으로
      직결된다. `CREATE INDEX CONCURRENTLY`는 이 락 없이(대신 테이블을
      두 번 스캔하는 비용으로) 인덱스를 빌드할 수 있지만, Postgres가
      트랜잭션 블록 안에서 `CONCURRENTLY`를 실행하는 것 자체를 허용하지
      않는다 - alembic이 정확히 이런 경우를 위해 제공하는
      `op.get_context().autocommit_block()`으로 `create_index`/`drop_index`
      호출만 트랜잭션 밖에서 실행되도록 감쌌다(둘 다
      `postgresql_concurrently=True`). 이 브랜치는 아직 병합 전(기존
      PR #5)이라 이 마이그레이션이 실제 프로덕션 DB에 적용된 적이 없다는
      판단 하에, 되돌리기용 후속 마이그레이션을 새로 만드는 대신 이미
      존재하는 리비전 파일 자체를 수정했다(alembic은 리비전 ID만
      `alembic_version` 테이블에서 추적하고 파일 내용을 체크섬으로
      검증하지 않으므로, 아직 이 리비전을 적용한 적 없는 환경에서는
      안전하게 반영됨).

      로컬 Postgres 16 클러스터에 연결해 실제로 검증했다 - `alembic
      downgrade -1`로 `DROP INDEX CONCURRENTLY`가 성공하는지,
      `alembic upgrade head`로 `CREATE INDEX CONCURRENTLY`가 성공하는지
      확인했고(둘 다 트랜잭션 밖에서 정상 실행됨), `psql \d
      knowledge_chunks`로 인덱스가 정확한 컬럼 순서(`user_id`,
      `embedding_model`, `created_at`)로 실제로 만들어졌는지 확인했다.
      `alembic revision --autogenerate`로 드리프트가 없는지(빈 마이그레이션
      생성 후 삭제), `alembic check`로도 추가 검증했다. 이 변경은 오직
      Postgres 실행 경로에만 영향을 주고(SQLite 기반 테스트는
      `Base.metadata.create_all()`을 직접 써서 alembic을 아예 안 거침)
      스키마 결과 자체는 이전과 동일해 애플리케이션 테스트 회귀는
      필요 없다고 판단했다 - 전체 413개 테스트 통과(변경 없음),
      전체 커버리지 99%, mypy 클린(`migrations/` 디렉터리도 별도로
      `mypy migrations` 확인). API 응답 형태/스키마 결과에 영향이
      없는 순수 마이그레이션 실행 방식 개선이라
      `docs/FRONTEND_INTEGRATION.md` 갱신은 필요 없었다.

## 백로그 (116라운드)

- [x] 140. CI(`.github/workflows/ci.yml`)에 배포 설정 파일(`docker-compose.yml`/
      `Caddyfile`) 검증이 전혀 없던 문제 수정. 113/114라운드가 바로 이 두
      파일에서 실제 배포 사고(`ENVIRONMENT`가 컨테이너에 전달되지 않아
      프로덕션에서도 `/docs`가 공개로 열려 있던 문제, Caddy가 `/metrics`를
      경로 제한 없이 공개로 프록시하던 문제)를 찾아 고쳤는데, 정작 CI의
      `test`/`migrations` job은 `app/`과 `migrations/`만 다루고 이 배포
      파일들은 사람이 리뷰할 때만 걸러지는 사각지대였다 - 같은 유형의
      실수가 재발해도 CI가 못 잡는 구조였다. `test`/`migrations` job과
      나란히 새 `deploy-config` job을 추가해 `docker compose config`
      (YAML/스키마 구조가 깨졌는지, `${VAR:?...}`로 필수 처리된 변수가
      실제로 채워졌는지)와 `caddy validate`(Caddyfile 문법 자체의 유효성)
      두 스텝을 돌리게 했다 - 이 둘은 113/114라운드에서 만든
      `tests/test_docker_compose.py`/`tests/test_caddyfile.py`(특정 문구가
      파일에 있는지만 보는 텍스트 검증)와는 서로 다른 종류의 회귀를
      잡는 상호 보완 관계다(예: `docker compose config`는 변수가
      `environment:` 목록에서 통째로 빠지는 것까지는 못 잡지만 YAML
      들여쓰기가 깨지는 것은 잡고, 텍스트 검증은 그 반대).

      실제로 검증해봤다 - `docker compose config`는 로컬에서 daemon 없이도
      동작해서(순수 클라이언트 사이드 YAML 처리) 직접 실행, 필수 변수가
      빠지면 정확히 종료 코드 1로 실패하는 것과 정상 실행 시 성공하는 것
      둘 다 확인했다. `docker run`은 이 세션 환경에 docker daemon이 없어
      직접 실행은 못 했지만, `caddy validate` 자체는 115라운드에서 이미
      실제 Caddy 2.6.2 바이너리(.deb에서 추출)로 검증해뒀다 - CI job의
      `docker run --entrypoint caddy caddy:2-alpine validate ...` 커맨드는
      이미지의 기본 ENTRYPOINT/CMD가 뭐든 상관없이 정확히 `caddy validate
      ...`가 실행되도록 `--entrypoint`로 명시했다(공식 이미지 관례를 그대로
      믿는 대신 모호함 자체를 없앰). `.github/workflows/ci.yml` 자체의
      YAML 문법도 `python3 -c "import yaml; yaml.safe_load(...)"`로 직접
      확인했다. `tests/test_ci_workflow.py`를 새로 만들어
      `test_ci_validates_docker_compose_and_caddyfile`(두 검증 스텝이
      워크플로 파일에 그대로 있는지)을 추가했고, `git stash`로 워크플로
      수정만 되돌리면 정확히 실패하는 것까지 확인했다. 전체 414개 테스트
      통과, 전체 커버리지 99%, mypy 클린. CI 파이프라인 구성만 바뀐
      변경이라 애플리케이션 코드/API 응답 형태에 영향이 없어
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (117라운드)

- [x] 141. `docker-compose.yml`의 5개 서비스(haruhan-backend/redis/prometheus/
      grafana/caddy) 어디에도 로그 로테이션 설정이 없던 문제 수정. Docker의
      기본 로깅 드라이버(`json-file`)는 `max-size`/`max-file`을 지정하지
      않으면 로그 파일 크기에 상한이 없다 - `Dockerfile`의 CMD(`uvicorn ...`)
      에 `--no-access-log`가 없어 uvicorn 기본 access log(요청마다 1줄)가
      stdout으로 계속 쌓이는데, 로테이션이 없으니 디스크가 서서히 채워진다.
      즉각적인 문제는 아니지만 운영 개월 수가 쌓일수록 확실히 터지는
      유형이고, 결국 디스크가 가득 차면 Caddy 인증서 갱신 실패나 DB 쓰기
      실패로 스택 전체가 조용히 멈출 수 있다. 최상위 `x-logging` YAML
      앵커(`driver: json-file`, `max-size: "10m"`, `max-file: "3"`)를 추가해
      5개 서비스 전부가 `logging: *default-logging`으로 공유하도록 했다 -
      값 하나를 한 곳에서만 관리하면 되고, 새 서비스가 추가돼도 앵커를
      까먹지 않는 한 자동으로 적용된다. `docker compose config`로 앵커가
      5개 서비스 전부에 정확히 풀리는지(YAML 파싱만이 아니라 docker
      compose 자신의 스키마 해석으로) 직접 확인했다.

      `tests/test_docker_compose.py`에
      `test_every_service_has_log_rotation_configured`를 추가했는데,
      기존 두 테스트(`ENVIRONMENT`/`LOG_LEVEL`)와 달리 이번엔 파일을
      `PyYAML`로 실제로 파싱해 모든 서비스 각각에 `logging.driver`/
      `logging.options.max-size`/`max-file`이 다 있는지 확인한다(단순
      텍스트 포함 여부만 보면 "5개 중 1개에만 로테이션이 있어도" 통과해버려
      의미가 없음). `git stash`로 `docker-compose.yml` 수정만 되돌리면
      정확히 실패하는 것까지 확인했다. `PyYAML`이 지금까지 이 저장소의
      직접적인 의존성으로 선언된 적이 없었다는 것도 확인해서(이 세션
      환경엔 어쩌다 설치돼 있었을 뿐, `requirements-dev.txt`에 없으면 CI
      환경에서 이 테스트가 `ModuleNotFoundError`로 깨질 수 있었음)
      `requirements-dev.txt`에 `PyYAML==6.0.3`을 명시적으로 추가했다 -
      `pip-audit`로 알려진 취약점이 없는 것도 확인했다. 전체 415개 테스트
      통과, 전체 커버리지 99%, mypy 클린. 순수 배포 설정/CI 의존성 수정이라
      애플리케이션 코드/API 응답 형태에 영향이 없어
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (118라운드)

- [x] 142. `docker-compose.yml`의 5개 서비스 어디에도 CPU/메모리 리소스
      상한이 없던 문제 수정. `redis`만 `--maxmemory 64mb`로 자체 상한이
      있고 나머지 4개(haruhan-backend/prometheus/grafana/caddy)는
      무제한이었다 - `haruhan-backend`는 `mindul-net`이라는 외부 공유
      네트워크에도 물려 있다는 주석("Ollama 등 다른 스택과 같은 네트워크")
      으로 보아 이 호스트는 다른 스택과 리소스를 공유하는 것으로 보이는데,
      FastAPI 프로세스의 메모리 누수나 Prometheus의 라벨 카디널리티
      폭증(예: 실수로 사용자별 값이 라벨에 섞이는 버그) 한 번이면 호스트
      전체 메모리를 잠식해 같은 호스트의 다른 스택(Ollama 포함)까지 함께
      죽일 수 있었다.

      다른 인프라 수정들(로그 로테이션, 배치 상한 등)과 달리 이 항목은
      순수하게 방어적이기만 한 변경이 아니라는 점을 판단 과정에서 먼저
      짚었다 - 상한을 너무 낮게 잡으면 정상적인 요청도 OOM으로 죽는
      새로운 장애를 만들 수 있어, "안 하는 것보다 나은가"가 자명하지
      않은 유일한 인프라 항목이었다. 이 세션은 이 시스템의 실제 운영
      트래픽/메모리 사용량에 대한 가시성이 전혀 없으므로, 타이트하게
      튜닝된 값 대신 95/99/131라운드와 같은 "넉넉한 안전장치, 주 방어선
      아님" 철학을 그대로 적용했다 - 개인/소규모 트래픽의 FastAPI
      프로세스가 정상적으로는 절대 안 닿을 만큼 넉넉하게(`haruhan-backend`
      1GB/2 CPU, `prometheus` 512MB/1 CPU, `grafana`/`caddy` 각 256MB/1 CPU,
      `redis`는 자체 `--maxmemory 64mb` 위에 여유를 둔 128MB/1 CPU) 잡아서,
      평소엔 절대 안 걸리고 진짜 폭주할 때만(예: 수 GB 이상 새는 심각한
      버그) 막는 서킷 브레이커로 설계했다 - 실사용 데이터가 쌓이면
      운영자가 더 타이트하게 조정하면 된다는 것을 주석에 명시했다.
      `deploy.resources.limits`(Compose Specification - `version:` 필드가
      없는 이 파일에선 스웜 모드가 아니어도 `docker compose up`에 그대로
      적용됨)로 5개 서비스 전부에 추가했다.

      `docker compose config`로 다섯 값이 정확한 바이트 수(1GB→1073741824,
      512MB→536870912, 256MB→268435456, 128MB→134217728)로 해석되는지
      직접 확인했다. `tests/test_docker_compose.py`에
      `test_every_service_has_a_memory_limit`을 추가했고, `git stash`로
      `docker-compose.yml` 수정만 되돌리면 정확히 실패하는 것까지
      확인했다. 전체 416개 테스트 통과, 전체 커버리지 99%, mypy 클린.
      순수 배포 설정 수정이라 애플리케이션 코드/API 응답 형태에 영향이
      없어 `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요
      없었다.

## 백로그 (119라운드)

- [x] 143. `scripts/backfill_knowledge_chunks.py`(전체 이력을 RAG 색인
      대상으로 재색인하는 일회성 운영 스크립트)에 테스트가 전무하고
      실행 전 안전장치가 없던 문제 수정. 이 저장소는 커버리지 99%를
      유지할 만큼 테스트 문화가 강한데, 정작 "사람이 손으로 실행해서
      전체 이력을 재색인하는" - 즉 실수 시 파급력이 가장 큰 축에 속하는
      이 스크립트만 완전히 사각지대였다. 사용법 docstring도 그냥
      `DATABASE_URL=... python -m scripts.backfill_knowledge_chunks`
      뿐이라, 운영자가 실수로 `.env`를 안 바꾼 로컬 셸에서 프로덕션
      `DATABASE_URL`을 그대로 물고 있는 상태로 돌리면 전체 테이블을
      훑으며 Ollama 임베딩 호출을 순차로 수천 번 날리는 것을 막을
      방법이 전혀 없었다.

      두 가지를 고쳤다. (1) 엔진/세션 생성과 실제 색인 로직을 분리해
      `backfill_all_content(session, rag_service)`로 뽑아냈다(스케줄러
      버전 `rag_backfill_service.backfill_unindexed_content`와 같은
      분리 이유 - 테스트가 인프라 준비 없이 로직만 검증할 수 있게).
      이 스크립트는 스케줄러 버전과 달리 "아직 색인 안 된 것만"이
      아니라 전체 이력을 대상으로 하므로(일회성 전체 재색인이 목적)
      그 차이도 회귀 테스트로 직접 확인했다. (2) 실행 전 대상 DB(비밀번호는
      가리고 호스트:포트/DB이름만) 를 보여주고 `y`가 아니면 취소하는
      `_confirm_before_running()`을 추가했다 - cron/CI 같은 비대화형
      환경에서는 `--yes`/`-y` 플래그로 건너뛸 수 있다.

      새 파일 `tests/test_backfill_knowledge_chunks.py`에 4개 테스트 추가:
      `_redact_database_url`이 비밀번호를 실제로 가리는지, 확인 프롬프트가
      `y`에서만 진행하고 그 외(빈 입력/`n`/`yes`처럼 정확히 `y`가 아닌
      모든 값)에서는 취소하는지(주입한 `ask` 함수로 실제 `input()` 없이
      테스트), 그리고 `backfill_all_content`가 이미 색인된 항목까지
      포함해 전체 이력을 정확히 재색인하는지(스터디 세션에서 파생된
      퀴즈는 원본이 이미 study_message 쪽에 있어 제외되는 것까지). `git
      stash`로 스크립트 수정만 되돌리면 새 함수들이 아예 없어서 임포트
      단계부터 정확히 실패하는 것까지 확인했다.

      검증 중에 117라운드가 만든 실제 버그도 하나 잡았다 - CI는
      `mypy app tests`를 돌리는데 그 라운드에서 나는 `mypy app`만
      돌려 확인했었다(다른 라운드들의 관행을 그대로 따랐을 뿐 CI의
      정확한 커맨드를 재현하지 않음). `mypy app tests`를 실제로 돌려보니
      `test_docker_compose.py`의 `import yaml`이 "Library stubs not
      installed"로 실패했다 - `PyYAML`은 런타임 패키지만 추가했지 mypy용
      타입 스텁 패키지(`types-PyYAML`)는 안 넣어서, 그 라운드부터 CI의
      mypy 스텝이 계속 깨져 있었을 것이다. `requirements-dev.txt`에
      `types-PyYAML==6.0.12.20260815`를 추가해 바로잡았다(`pip-audit`
      확인도 통과). 이번 라운드부터는 `mypy app tests scripts`로 CI와
      정확히 같은 대상을 확인하는 것으로 검증 관행을 갱신했다. 전체
      420개 테스트 통과, 전체 커버리지 99%(`scripts/`는 `--cov=app`
      범위 밖이라 커버리지 수치엔 안 잡히지만 새 테스트로 핵심 로직은
      검증됨), mypy 클린. 스크립트 사용법(새 `--yes` 플래그)만 추가된
      순수 확장이라 API 응답 형태에 영향이 없어
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (120라운드)

- [x] 144. `docker-compose.yml`의 `haruhan-backend` `environment:` 목록이
      `Settings` 필드 대부분을 컨테이너에 전달하지 않던 문제 수정. 113라운드가
      `ENVIRONMENT`/`LOG_LEVEL` 두 개가 이 목록에서 빠져 있던 걸 고쳤는데,
      `Settings` 필드를 하나하나 대조해보니 그 뒤로도 17개가 더 같은
      이유로 빠져 있었다 - `.env`에 값을 채워도 이 목록에 없는 변수는
      컨테이너에 전혀 전달되지 않고 코드 기본값으로 조용히 fallback되는
      상태였다. 특히 `AUTH_RATE_LIMIT`(브루트포스 방어), `MAX_BODY_SIZE_BYTES`
      (요청 바디 크기 DoS 방어), `WS_IDLE_TIMEOUT_SECONDS`/
      `MAX_CONCURRENT_WS_CONNECTIONS`(WS DB 커넥션 풀 고갈 방지, 99라운드에서
      집중 설계) 같은 여러 라운드에 걸쳐 만든 안전장치들이 실제 배포
      경로에서는 운영자가 조정할 방법이 없는 죽은 설정이었다. 나머지
      13개(`AUTH_RATE_LIMIT`/`EXPORT_RATE_LIMIT`/`MODELS_RATE_LIMIT`/
      `MAX_CHAT_HISTORY_MESSAGES`/`MAX_QUIZ_SOURCE_LENGTH`/
      `DEFAULT_QUIZ_QUESTION_COUNT`/`MAX_QUIZ_QUESTION_COUNT`/
      `MAX_QUIZ_CHOICE_COUNT`/`RAG_BACKFILL_BATCH_SIZE`/
      `MAX_INTERVIEW_QUESTIONS`/`MAX_REVIEW_CONTENT_LENGTH`/`EMBEDDING_MODEL`/
      `RAG_TOP_K`/`RAG_MAX_CANDIDATE_CHUNKS`/`WS_IDLE_TIMEOUT_SECONDS`/
      `MAX_CONCURRENT_WS_CONNECTIONS`/`MAX_BODY_SIZE_BYTES`)를 기존
      패턴(`${VAR:-default}`, `.env.example`과 같은 기본값)대로 추가했다.
      곁들여 `.env.example`에서도 `export_rate_limit` 필드만 유일하게
      문서화가 빠져 있던 걸 발견해(`EXPORT_RATE_LIMIT=10/minute`) 같이
      채웠다.

      `docker compose config`로 haruhan-backend의 최종 `environment` 맵을
      파이썬으로 직접 파싱해, 30개 변수 전부가 정확한 기본값으로 해석되는지
      확인했다. 이번엔 이 17개만 텍스트로 하나하나 확인하는 대신,
      `tests/test_docker_compose.py`에
      `test_every_env_example_setting_reaches_haruhan_backend_container`를
      추가해 "`.env.example`에 문서화된 모든 설정(`DOMAIN`/
      `GRAFANA_ADMIN_PASSWORD`처럼 compose 자체에서만 쓰고 앱은 안 읽는
      것 제외)이 `docker-compose.yml`의 `environment:` 목록에도 전부
      있는지"를 일반화해서 검증한다 - 앞으로 새 `Settings` 필드를
      추가하면서 `.env.example`에는 넣고 `docker-compose.yml`에는
      빠뜨리는 이 클래스의 회귀 전체를 영구히 막는다(개별 변수 하나마다
      테스트를 새로 추가할 필요가 없어짐). `git stash`로
      `docker-compose.yml`/`.env.example` 수정만 되돌리면 정확히
      실패(누락된 16개 변수 목록까지 에러 메시지에 나열)하는 것까지
      확인했다. 전체 421개 테스트 통과, 전체 커버리지 99%, mypy 클린.
      순수 배포 설정 수정이라 애플리케이션 코드/API 응답 형태에 영향이
      없어 `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요
      없었다.

## 백로그 (121라운드)

- [x] 145. 학습챗 메시지 전송이 REST(`POST
      /study/sessions/{id}/messages`)와 WS(`stream_message`) 두 경로로
      들어오는데, 공백만 있는 `content`에 대해 서로 다르게 동작하던 문제
      수정. WS 경로는 이미 `not content.strip()`으로 걸러 "content는 비어
      있을 수 없습니다" 에러 이벤트를 보내고 LLM을 아예 호출하지 않는데,
      REST 경로의 `StudyMessageCreateRequest.content`는 `min_length=1`만
      체크해 `" "` 같은 공백 문자열을 그대로 통과시켰다 - 빈 메시지가 실제
      `StudyMessage` 행으로 저장되고, 그 뒤 불필요한 Ollama 호출까지
      발생했다(동일 기능의 두 진입점이 같은 잘못된 입력에 대해 다르게
      반응하는 상태). `app/schemas/study.py`의 기존
      `validate_content_length` field_validator에 `value.strip()`이 빈
      문자열이면 WS와 동일한 문구로 거부하는 체크를 앞에 추가해 REST를 WS
      쪽 동작에 맞췄다.

      `interview_practice.answer`/`interview_review.content`/
      `quiz.source_text` 등 다른 스키마에도 같은 `min_length=1`-only 패턴이
      있지만, 이번 라운드는 REST/WS 두 경로가 동일 기능에 대해 실제로 다르게
      동작하는 `study.py` 케이스만 고쳤다 - 나머지는 대응하는 WS 구현이
      따로 없어 "드리프트"가 존재하지 않으므로 범위를 넓히지 않았다(더 큰
      후속 작업으로 남김).

      `tests/test_study.py`에
      `test_send_message_rejects_whitespace_only_content`를 추가해 공백만
      있는 `content`가 422로 거부되고 세션에 메시지가 전혀 저장되지 않는
      것까지 확인했다. `git stash`로 `app/schemas/study.py` 수정만
      되돌리면 정확히 실패(200 OK로 빈 메시지가 저장됨)하는 것까지
      확인했다. 전체 422개 테스트 통과, 전체 커버리지 99%(`app/schemas/
      study.py`는 100%), `mypy app tests scripts` 클린. 순수 검증 강화라
      기존 API 계약(성공 시 응답 형태)에는 변화가 없어(422 에러 케이스만
      추가) `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요
      없었다.

## 백로그 (122라운드)

- [x] 146. 학습챗/퀴즈/면접연습/면접복기의 목록에 그대로 노출되는 라벨
      필드(제목/주제/회사명/직무명)가 공백-only 값을 그대로 통과시키던
      문제 수정. `title`/`topic`/`company`/`position`은 전부
      `Field(..., min_length=1, max_length=255)`만 쓰고 있었는데,
      `min_length=1`은 빈 문자열(`""`)만 막을 뿐 `"   "`처럼 공백만 있는
      값은 그대로 통과시켰다 - 이 필드들은 121라운드에서 고친 학습챗
      `content`와 달리 LLM에 보내는 프롬프트가 아니라 세션/퀴즈/면접연습
      세션/면접복기 **목록 화면에 그대로 노출되는 제목/식별 라벨**이라,
      공백-only 값이 저장되면 목록에서 다른 항목과 전혀 구별할 수 없는
      빈 줄처럼 보이는 항목이 생겨 사용자가 원하는 항목을 찾을 방법이
      없어진다.

      영향받은 필드 7개: `StudySessionCreateRequest.title`/
      `StudySessionUpdateRequest.title`(`app/schemas/study.py`),
      `QuizCreateRequest.title`/`QuizUpdateRequest.title`
      (`app/schemas/quiz.py`), `InterviewPracticeCreateRequest.topic`
      (`app/schemas/interview_practice.py`),
      `InterviewReviewCreateRequest.company`/`.position`/
      `InterviewReviewUpdateRequest.company`/`.position`
      (`app/schemas/interview_review.py`, Update 쪽은 선택 필드라
      `None`은 그대로 허용).

      기존 `app/schemas/validators.py`의 `NormalizedEmail` 패턴(공용
      `AfterValidator` + `Annotated` 타입)을 그대로 따라 `NonBlankStr`
      타입을 추가했다 - `value.strip()`이 빈 문자열이면 거부하고, 통과 시
      원본 값은 그대로 반환한다(앞뒤 공백을 트리밍하지는 않음, 121라운드의
      `content` 수정과 동일한 최소 범위). 7개 필드 전부
      `NonBlankStr = Annotated[str, AfterValidator(_reject_blank)]`로
      타입을 바꾸고 기존 `Field(min_length=1, max_length=255)` 제약은
      그대로 유지했다 - `Annotated` 위에 `Field`를 얹으면 길이 제약이
      먼저 적용되고 그 결과에 `AfterValidator`가 이어서 적용되는 것을
      직접 확인했다(`Optional[NonBlankStr]`도 `None`은 그대로 통과,
      문자열이면 검증기가 적용되는 것까지 확인).

      `interview_practice.answer`/`interview_review.content`/
      `quiz.source_text`처럼 프롬프트로 쓰이는 필드는 이번 라운드에서도
      건드리지 않았다 - 120/121라운드가 이미 "대응하는 WS 구현이 없어
      드리프트가 없다"는 이유로 범위 밖으로 명시했고, 이번 라운드가 고친
      건 완전히 다른 사유(목록 UX)라 별개다.

      `tests/test_schemas_validators.py`에
      `test_whitespace_only_label_field_is_rejected`(7개 필드
      전부 parametrize)와
      `test_interview_review_update_allows_omitted_but_rejects_whitespace_only_company`
      를 추가했다. `git stash`로 `app/schemas/validators.py`와 7개 필드
      수정만 되돌리면 8개 테스트 케이스 전부가 정확히 실패(공백-only
      값이 그대로 통과)하는 것까지 확인했다. 전체 430개 테스트 통과,
      전체 커버리지 99%(`app/schemas/validators.py`/`study.py`/
      `quiz.py`/`interview_practice.py`는 100%), `mypy app tests
      scripts` 클린. 순수 검증 강화(성공 시 응답 형태는 그대로, 422
      에러 케이스만 늘어남)라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (123라운드)

- [x] 147. 레이트리밋 저장소(Redis) 응답이 느려지는 상황(연결 자체가
      거부되는 완전 장애가 아니라 패킷 유실 등으로 응답만 지연되는 경우)에서
      이벤트 루프 전체가 최대 5초씩 멈출 수 있던 문제 완화.
      `app/core/rate_limit.py`가 쓰는 `slowapi.Limiter`는 내부적으로
      `limits` 라이브러리의 `RedisStorage`를 쓰는데, 이 스토리지는 동기
      `redis-py` 클라이언트를 그대로 감싸고 있고, `slowapi`는
      `@limiter.limit()` 데코레이터 안에서 그 `hit()` 호출을 `await` 없이
      동기로 실행한다(`slowapi/extension.py`의 `__evaluate_limits`가 일반
      `def`이고, 이걸 호출하는 `async_wrapper`는 그 호출 결과를 기다리는
      동안 이벤트 루프에 제어권을 넘기지 않음 - 직접 소스를 읽어 확인).
      `Dockerfile`이 `uvicorn`을 워커 1개로 띄우므로(`--workers` 플래그
      없음), 이 블로킹 호출이 그 프로세스의 유일한 이벤트 루프 스레드를
      그대로 막는다. 이 앱은 auth/chat/study/quiz/interview/export 등
      거의 모든 쓰기 엔드포인트에 `@limiter.limit()`이 걸려 있어서,
      영향 범위가 사실상 전체 API다.

      `redis-py==8.0.1`의 `socket_timeout`/`socket_connect_timeout` 기본값이
      5초라는 걸 직접 확인했다(`redis/_defaults.py`의
      `DEFAULT_SOCKET_TIMEOUT = 5`) - `ConnectionError`로 즉시 잡히는
      완전 장애(포트가 닫혀 연결 자체가 거부되는 경우, 기존
      `test_limiter_falls_back_to_memory_when_redis_unreachable` 등이
      이미 다루는 시나리오)는 이 문제와 무관하다. 문제는 Redis가 응답만
      느려지는 경우(네트워크 혼잡, GC 일시정지 등) - 명시적으로 타임아웃을
      설정하지 않으면 요청 하나가 실제로 응답을 받거나 소켓 타임아웃이 날
      때까지(최대 5초) 프로세스 전체가 멈춘다.

      `Limiter(...)` 생성 시 `storage_options`로
      `socket_connect_timeout`/`socket_timeout`을 1초로 명시했다(다른
      안전장치들과 같은 "정상 사용량보다 훨씬 넉넉하지만 무한정은 아닌"
      상한 철학, 95/99/118/131라운드 - 로컬 Redis 왕복은 보통 1ms 미만이라
      1초는 압도적으로 넉넉하면서도 최악의 경우 정지 시간을 5초에서 1초로
      줄인다). `MemoryStorage`(REDIS_URL 미설정 시 기본 경로)는 여분의
      키워드 인자를 그냥 무시하므로(`**_: str`), 이 옵션을 항상 전달해도
      Redis를 안 쓰는 배포에는 영향이 없는 것까지 직접 확인했다. slowapi의
      `storage_options` 타입 힌트가 `Dict[str, str]`이라 정수를 넣으면
      mypy가 거부하는데, 실제로는 그대로 `redis.from_url(...)`에
      `**kwargs`로 전달될 뿐이라 런타임에는 문제없다는 것도 직접 Limiter를
      만들어 커넥션 풀의 `connection_kwargs`까지 확인한 뒤, 업스트림 타입
      힌트 오류로 판단해 `# type: ignore[dict-item]`로 좁게 처리했다
      (`app/repositories/*_repository.py`의 `result.rowcount` 등 기존
      코드베이스에도 있는 패턴).

      WebSocket 경로(`check_rate_limit()`)가 직접 호출하는
      `limiter.limiter.hit()`도 같은 `Limiter` 인스턴스의 저장소를 쓰므로
      별도 수정 없이 같은 타임아웃 상한을 그대로 적용받는다 - 소켓 타임아웃은
      호출 지점이 아니라 연결 객체 레벨에서 적용되기 때문이다.

      `tests/test_rate_limit_redis.py`에
      `test_redis_storage_has_bounded_socket_timeouts`(프로덕션 코드와 같은
      `storage_options`로 만든 `Limiter`의 redis 커넥션 풀에 타임아웃 값이
      실제로 전달되는지, 서버 연결 없이 확인 - `limits`는 스토리지 생성
      시점엔 연결하지 않고 지연 연결하므로 Redis 서버가 없어도 통과)와
      `test_app_rate_limiter_has_bounded_socket_timeouts_configured`(앱
      전체가 공유하는 실제 `rate_limit_module.limiter` 인스턴스가 이
      옵션을 들고 있는지)를 추가했다. `git stash`로
      `app/core/rate_limit.py` 수정만 되돌리면 두 테스트 모두 정확히
      실패(`REDIS_SOCKET_TIMEOUT_SECONDS` 상수 자체가 없어
      `AttributeError`)하는 것까지 확인했다. 네트워크를 실제로 블랙홀
      상태로 만들어 5초 대 1초 정지 시간을 직접 재는 테스트는 샌드박스
      환경에서 안정적으로 재현하기 어려워 작성하지 않았다 - 대신 실제로
      적용되는 타임아웃 값 자체가 설정돼 있는지를 검증한다.

      전체 432개 테스트 통과, 전체 커버리지 99%(`app/core/rate_limit.py`
      포함 변경 파일 전부 커버리지 저하 없음), `mypy app tests scripts`
      클린. 레이트리밋 동작 자체(허용/거부 판정)는 그대로라 API 응답
      형태에 영향이 없어 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (124라운드)

- [x] 148. `MaxBodySizeMiddleware`가 413을 직접 응답할 때 CORS/보안 헤더가
      전혀 안 붙던 문제 수정. `app/main.py`는 `CORSMiddleware` →
      `SecurityHeadersMiddleware` → `MaxBodySizeMiddleware` 순으로
      `add_middleware`를 호출하고 있었는데, Starlette의
      `add_middleware`는 나중에 등록할수록 더 바깥쪽으로 앱을 감싸므로
      (직접 `Starlette.add_middleware`/`build_middleware_stack` 소스를
      읽어 확인: `user_middleware.insert(0, ...)` 후
      `reversed(middleware)` 순서로 wrap), 실제 실행 순서는
      `MaxBodySizeMiddleware`가 `CORSMiddleware`/`SecurityHeadersMiddleware`
      보다 바깥이었다. `MaxBodySizeMiddleware`는 본문 크기 초과 시 안쪽
      앱(라우터는 물론 CORS/보안 헤더 미들웨어까지)을 아예 호출하지 않고
      자기 자신이 413 응답을 완성해버리므로, 그 두 미들웨어를 완전히
      건너뛴 채 응답이 나갔다.

      `Origin` 헤더를 넣어 대용량 payload를 cross-origin 요청으로 보내
      직접 재현 확인 - 수정 전에는 413 응답에 `content-length`/
      `content-type`만 있고 `access-control-allow-origin`/
      `x-content-type-options`/`cache-control` 등이 전부 빠져 있었다.
      이 프로젝트의 실제 배포 형태는 Vercel에 배포된 프론트가 다른
      도메인의 이 API를 호출하는 cross-origin 구조라(61번 항목이
      `expose_headers` 누락을 고친 것과 같은 배포 형태) 실사용에도
      영향이 있다 - 브라우저는 CORS 헤더가 없는 응답을 자바스크립트가
      읽지 못하게 막으므로, 사용자는 "메시지가 너무 깁니다"라는 실제
      에러 메시지(60번 항목이 통일한 에러 포맷) 대신 원인을 알 수 없는
      네트워크 오류만 보게 된다. 정적 자산이 없는 순수 API 서버 전체에
      일괄 적용되는 `SecurityHeadersMiddleware`의 표준 브라우저 보안
      헤더도 마찬가지로 이 응답 하나만 예외적으로 빠지고 있었다.

      `app.add_middleware(MaxBodySizeMiddleware, ...)` 호출을 `CORSMiddleware`/
      `SecurityHeadersMiddleware`보다 먼저(=더 안쪽으로) 옮겼다.
      "본문을 읽기 전에 크기부터 차단한다"는 이 미들웨어의 원래 목적은
      그대로 유지된다 - 실제로 본문을 읽는 건 여전히 이 미들웨어보다
      더 안쪽인 라우터/엔드포인트뿐이고, CORS/보안 헤더 미들웨어는 둘 다
      요청 본문을 읽지 않기 때문이다. `AccessLogMiddleware`/
      `MetricsMiddleware`(전체 왕복 시간을 재려고 의도적으로 가장
      바깥쪽에 둔 두 미들웨어, 111라운드 주석 참고)의 상대적 위치는
      건드리지 않았다.

      `tests/test_middleware.py`에
      `test_body_size_limit_response_still_carries_cors_and_security_headers`
      를 추가해, `Origin` 헤더가 있는 대용량 payload 요청의 413 응답에
      `access-control-allow-origin`/`x-content-type-options`/
      `cache-control` 헤더가 실제로 붙는지 확인했다. `git stash`로
      `app/main.py` 수정만 되돌리면 정확히 실패(헤더가 전혀 없음)하는
      것까지 확인했다. 전체 433개 테스트 통과, 전체 커버리지 99%,
      `mypy app tests scripts` 클린. 미들웨어 등록 순서만 바뀌었을 뿐
      각 미들웨어의 동작/응답 바디 형태는 그대로라 `docs/
      FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (125라운드)

- [x] 149. `GET /health/ready`가 인증도 레이트리밋도 캐시도 없이, 호출될
      때마다 Ollama에 실제 HTTP 요청을 보내던 문제 수정. 이 엔드포인트는
      "트래픽 라우팅 판단용"이라 로그인 절차를 둘 수 없어 애초에 인증이
      없는데(`app/api/v1/routes/health.py` 자신의 docstring이 이미 그렇게
      설명함), `Caddyfile`은 `/metrics`만 막고 나머지는 전부 공개
      도메인으로 그대로 프록시하며(138라운드), `docker-compose.yml`의
      `healthcheck`도 `/health`(생존 확인만)만 찌르지 `/health/ready`는
      건드리지 않는다는 것까지 직접 확인했다 - 즉 이 엔드포인트는 익명
      호출자가 원하는 만큼 반복 호출할 수 있는 상태였고, 매 호출마다
      `check_ollama_health()`가 실제 Ollama 서버에 모델 목록 조회 요청을
      보내고 `REDIS_URL`이 설정된 경우 Redis 커넥션까지 새로 열었다
      닫았다. 121라운드가 `/models`("이 앱에서 유일하게 인증 없이 공개된
      엔드포인트")에서 고친 것과 정확히 같은 모양의 문제를, 그 라운드의
      스윕이 놓쳤던 형제 엔드포인트에서 뒤늦게 발견한 것이다.

      다만 `/models`와 달리 이 엔드포인트는 오케스트레이터/업타임
      모니터가 몇 초 간격으로 폴링하는 게 정상적인 사용 패턴이라,
      `/models`처럼 레이트리밋(`@limiter.limit`)을 걸면 정상적인 헬스체크
      폴링 자체가 429로 거부돼 멀쩡한 인스턴스가 "unready"로 잘못
      판정되는 새로운 위험이 생긴다고 판단했다 - 그래서 레이트리밋 대신
      `/models`가 쓰는 것과 같은 `TTLCache` + `asyncio.Lock` 패턴(캐시가
      막 만료된 순간 동시에 들어온 요청들이 각자 상류 서비스를 호출하는
      것까지 막음)을 그대로 재사용해 5초간 결과를 캐싱했다 - 호출
      빈도와 무관하게 실제 DB/Redis/Ollama 확인은 이 주기당 한 번만
      일어나면서도, 트래픽 라우팅 판단에 쓰기에 충분히 신선한 값을
      유지한다.

      `tests/conftest.py`의 전역 `_reset_state` autouse 픽스처에도
      `_models_cache.clear()`와 같은 자리에 `_readiness_cache.clear()`를
      추가해 테스트 간 캐시가 새지 않게 했다(안 했으면 한 테스트가 채운
      캐시를 다른 테스트가 그대로 받아가는 오염이 실제로 재현됐다).
      `tests/test_health.py`에 `test_readiness_caches_result_within_ttl`
      (반복 호출해도 Ollama 호출이 정확히 1번만 일어나는지)과
      `test_get_or_check_readiness_coalesces_concurrent_cache_misses`
      (`/models`의 같은 이름 테스트와 동일한 이유로, 캐시가 비어있는
      상태에서 동시에 5개 호출이 들어와도 실제 확인은 1번만 일어나는지)
      를 추가했다. `git stash`로 `app/api/v1/routes/health.py`와
      `tests/conftest.py` 수정만 되돌리면 캐싱 테스트가 정확히
      실패(`call_count == 2`)하는 것까지 확인했다. 전체 435개 테스트
      통과, 전체 커버리지 99%(`app/api/v1/routes/health.py` 100% 포함),
      `mypy app tests scripts` 클린. 응답 바디 형태(정상/장애 시 필드
      구성)는 그대로고 순수 캐싱 계층 추가라 `docs/
      FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (126라운드)

- [x] 150. 면접 연습 답변 제출(`submit_answer`)이 Ollama의 구조적 JSON
      출력이 스키마 검증에 실패하면 재시도 없이 바로 502로 실패하던 문제
      수정. `generate_json()`(스키마를 강제하는 게 아니라 "부탁"만 하는
      구조적 출력 호출)을 쓰는 곳은 이 코드베이스에 딱 두 군데뿐인데,
      `quiz_service._generate_quiz`는 8번 라운드에서 이미 "모델이 스키마에
      안 맞는 JSON을 뱉으면 같은 프롬프트로 한 번 더 시도"하는 재시도를
      넣었지만(`_MAX_QUIZ_GENERATION_ATTEMPTS = 2`), 나머지 한 곳인
      `interview_practice_service.submit_answer`은 그 수정을 빠뜨리고
      `except (OllamaServiceError, ValidationError, json.JSONDecodeError):
      raise _GENERATION_FAILED`로 파싱 실패든 뭐든 첫 시도에 바로 포기하고
      있었다 - REST/WS 드리프트(121/145라운드), 레이트리밋/캐시 누락
      (121/149라운드)에 이어, "같은 메커니즘을 쓰는 형제 코드 중 하나만
      먼저 고쳐진" 패턴을 다시 한번 발견한 것이다.

      이 함수는 특히 영향이 크다 - `submit_answer`는 AI 호출을 답변
      커밋과 한 트랜잭션으로 묶어서(주석에 명시: "AI 호출이 실패하면 답변
      자체도 롤백되어 current_turn이 다시 미답변 상태로 남고, 그대로
      재시도하면 된다") 실패 시 방금 쓴 답변까지 통째로 날아가게
      설계했는데, 재시도가 없으니 일회성 파싱 글리치 하나로 사용자가 방금
      입력한 답변이 사라지고 레이트리밋(`chat_rate_limit`)을 다시 뚫어야
      하는 수동 재시도를 강제하고 있었다.

      `generate_json` 호출과 `_FeedbackWithNextQuestion.model_validate_json`
      파싱을 `_generate_feedback_and_next_question` 메서드로 분리하고,
      `quiz_service._generate_quiz`와 정확히 같은 재시도 루프 패턴(최대
      2회, `OllamaServiceError`는 즉시 실패 - 재시도해도 나아질 게 없음,
      `ValidationError`/`json.JSONDecodeError`만 재시도)을 적용했다.
      `tests/test_interview_practice.py`에 `tests/test_quiz.py`의
      `RecoversOnRetryOllamaService`/`MalformedJsonOllamaService`와 같은
      패턴으로 `RecoversOnRetryOllamaService`(첫 호출만 깨진 JSON, 재시도로
      복구)와 `AlwaysMalformedJsonOllamaService`(매번 깨진 JSON, 재시도
      2회 모두 소진 후 502)를 추가해 두 테스트를 작성했다. `git stash`로
      `app/services/interview_practice_service.py` 수정만 되돌리면
      재시도 성공 테스트가 정확히 실패(첫 호출에 바로 502)하는 것까지
      확인했다. 전체 437개 테스트 통과, 전체 커버리지 99%
      (`interview_practice_service.py` 100% 포함), `mypy app tests
      scripts` 클린. 최종 성공/실패 응답 형태는 그대로고 중간에 재시도
      횟수만 늘어난 것이라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (127라운드)

- [x] 151. `ACCESS_TOKEN_EXPIRE_MINUTES`/`REFRESH_TOKEN_EXPIRE_DAYS`에 양수
      검증이 없어, 0이나 음수로 설정하면 발급되는 토큰이 태어날 때부터
      이미 만료된 상태가 되던 문제 수정. `core/tokens.py`의
      `create_access_token()`은 `exp = now_ts + settings.
      access_token_expire_minutes * 60`을, `refresh_token_expiry()`는
      `utcnow_naive() + timedelta(days=settings.refresh_token_expire_days)`
      를 그대로 계산에 쓴다 - 둘 중 하나가 0이나 음수면(오타, 단위 착각
      등) 그 즉시 과거 시각이 `exp`로 박히거나 이미 지난 만료 시각이
      계산된다. `Settings()` 생성 자체는 성공해 앱도 정상적으로 뜨므로,
      로그인/회원가입 요청은 겉보기엔 멀쩡히 200을 반환하면서 발급한
      토큰만 곧바로 무효가 되는, 시작 시점에는 전혀 티가 안 나는 전면적인
      인증 장애로 이어진다 - `JWT_SECRET_KEY` 길이(1번대 라운드)/
      `LOG_LEVEL`/`ENVIRONMENT`(73/74라운드)/레이트리밋 문자열
      (100라운드)/퀴즈 문항 수 기본값(108라운드)처럼 이미 여러 라운드가
      막아온 "Settings 필드 하나가 시작 시점 검증 없이 조용히 앱을 망가진
      상태로 띄우는" 클래스의 남은 인스턴스였다.

      `app/core/config.py`에 `access_token_expire_minutes`/
      `refresh_token_expire_days` 두 필드를 함께 검증하는
      `field_validator`를 추가했다 - `<= 0`이면 어느 필드가 문제인지
      필드명을 포함한 메시지로 거부한다. `tests/test_config.py`에
      `test_settings_accepts_positive_token_expiry`/
      `test_settings_rejects_non_positive_token_expiry`(0/-1
      parametrize)를 추가했다. `git stash`로 `app/core/config.py`
      수정만 되돌리면 음수/0 케이스 4개 전부 정확히 실패
      (`ValidationError`가 안 남)하는 것까지 확인했다. 전체 443개 테스트
      통과, 전체 커버리지 99%(`app/core/config.py` 100% 포함), `mypy
      app tests scripts` 클린. 정상 범위(양수) 설정의 동작은 그대로라
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요
      없었다.

## 백로그 (128라운드)

- [x] 152. Ollama의 구조적 JSON 출력(`generate_json()`)에 공백뿐인
      문자열이 걸러지지 않고 그대로 저장되던 문제 수정 - 이 코드베이스에서
      `generate_json()`을 쓰는 두 곳(퀴즈 생성/면접 연습 답변 제출) 모두
      스키마는 `str` 타입만 보장할 뿐 non-blank는 강제하지 않는데, 문항
      수/보기 수 상한(108/132라운드)·정답이 보기에 있는지·보기 중복
      여부만 검증하고 각 문자열이 공백뿐인지는 지금까지 한 번도 걸러진
      적이 없었다. 148~151라운드에 걸쳐 4번 연속으로 후보로 떠올랐다가
      매번 더 시급한 다른 항목에 밀려 미뤄져 온 항목을, 이번 라운드에서
      이 항목보다 더 나은 후보가 없어 드디어 구현했다.

      `app/services/quiz_service.py`의 `_generate_quiz` 검증 게이트(`all
      (...)`)에 `q.question.strip()`/`q.explanation.strip()`/`all(choice.
      strip() for choice in q.choices)`를 추가했다 - 공백뿐인 문항/보기/
      해설이 있으면 기존 재시도 경로(최대 2회)를 그대로 타고, 재시도까지
      전부 실패하면 502로 끝난다.

      `app/services/interview_practice_service.py`의
      `_generate_feedback_and_next_question`(150라운드에서 quiz_service와
      같은 재시도 패턴을 이식한 메서드)에도 같은 이유로 파싱 성공 직후
      `parsed.feedback.strip()`/`parsed.next_question.strip()` 검증을
      추가했다 - 특히 `next_question`이 공백이면 그대로
      `InterviewPracticeTurn.question`으로 저장돼, 사용자가 답할 내용이
      아예 없는 빈 질문으로 진행 중인 면접 연습 세션이 조용히 멈춰버릴 수
      있었다(퀴즈 쪽보다 오히려 체감 임팩트가 더 크다고 판단해 같은
      라운드에 함께 고쳤다 - 121/145·122/146라운드처럼 "같은 원인이 여러
      곳에 있으면 한 라운드에 같이 정리"하는 기존 관례를 따름).

      `tests/test_quiz.py`에 `BlankChoiceOllamaService`(보기 중 하나가
      공백)와 `test_create_quiz_blank_choice_returns_502`를,
      `tests/test_interview_practice.py`에
      `AlwaysBlankNextQuestionOllamaService`와
      `test_submit_answer_returns_502_when_next_question_is_blank`를
      추가했다(둘 다 기존 `TooManyQuestionsOllamaService`/
      `AlwaysMalformedJsonOllamaService`와 같은 패턴). `git stash`로
      `quiz_service.py`/`interview_practice_service.py` 수정만
      되돌리면 두 테스트 모두 정확히 실패(퀴즈 쪽은 공백 보기가 그대로
      201로 생성됨, 면접 연습 쪽은 공백 질문이 그대로 200으로 저장됨)
      하는 것까지 확인했다. 전체 445개 테스트 통과, 전체 커버리지
      99%(`quiz_service.py`/`interview_practice_service.py` 둘 다 100%
      포함), `mypy app tests scripts` 클린. 최종 성공/실패 응답 형태는
      그대로고 검증 조건만 늘어난 것이라 `docs/FRONTEND_INTEGRATION.md`
      갱신도, 마이그레이션도 필요 없었다.

## 백로그 (129라운드)

- [x] 153. 면접 연습 세션에 이름 변경(`PATCH`) 엔드포인트가 없던 CRUD
      비대칭 해소. 학습챗 세션(`PATCH /study/sessions/{id}`)/퀴즈
      (`PATCH /quizzes/{id}`)/면접복기(`PATCH /interview/reviews/{id}`)
      는 전부 생성 후 제목/내용을 수정할 수 있는데, 면접 연습 세션
      (`topic`)만 유일하게 그 방법이 없어 오타를 고치거나 주제를
      재정리하려면 세션을 통째로 지우고 다시 만드는 수밖에 없었다 -
      150~152라운드에 걸쳐 3번 연속으로 후보로 떠올랐다가 매번 더 작은
      항목에 밀려 미뤄져 온 항목을, 이번 라운드에서 더 나은 후보가 없어
      드디어 구현했다.

      `StudySessionRepository.update_title`/`StudyService.rename_session`
      과 정확히 같은 패턴을 그대로 이식했다:
      `InterviewPracticeSessionRepository.update_topic`(속성만 바꾸고
      flush - `updated_at`은 모델의 `onupdate=func.now()`가 자동 갱신),
      `InterviewPracticeService.rename_session`(세션이 없거나 다른
      사용자 소유면 404), 새 `InterviewPracticeUpdateRequest` 스키마
      (122/146라운드가 추가한 `NonBlankStr`로 공백뿐인 주제를 이미
      막음), `PATCH /interview/practice-sessions/{session_id}` 라우트를
      `GET /{id}`와 `DELETE /{id}` 사이에 추가했다(`study.py`의 라우트
      순서와 동일). 이름 변경 자체는 AI 호출이 아니라서 다른 세
      PATCH들과 마찬가지로 레이트리밋을 걸지 않았다.

      `tests/test_interview_practice.py`에 `tests/test_study.py`의
      `test_rename_session`/`test_rename_session_rejects_empty_title`/
      `test_rename_session_404_for_nonexistent_session`/
      `test_rename_session_404_for_other_users_session`과 같은 패턴으로
      4개 테스트를 추가했다. `git stash`로 라우트/서비스/리포지토리/
      스키마 수정을 전부 되돌리면 4개 전부 정확히 실패
      (`405 Method Not Allowed` - 라우트 자체가 없었으므로)하는 것까지
      확인했다. `docs/FRONTEND_INTEGRATION.md`의 3-3(면접 연습) 표에
      새 PATCH 행을 추가했다 - 이번 라운드는 실제로 새 엔드포인트가
      생기는 경우라 갱신이 필요했다. 전체 449개 테스트 통과, 전체
      커버리지 99%(`interview_practice.py` 스키마/서비스/라우트 전부
      100% 포함), `mypy app tests scripts` 클린. 스키마/모델 변경 없이
      기존 컬럼(`topic`)을 수정하는 새 API 경로 추가라 마이그레이션은
      필요 없었다.

## 백로그 (130라운드)

- [x] 154. 퀴즈 제출 응답(`POST /quizzes/{id}/submit`)과 결과 조회
      (`GET /quizzes/{id}/result`)의 `answers` 배열이 실제 문항 순서
      (`order_index`)와 다르게 나올 수 있던 문제 수정. 요청 스키마
      (`QuizSubmitRequest.answers`)는 클라이언트가 문항 순서대로 답을
      제출하도록 강제하지 않는데, `quiz_service.submit_answers`는 채점
      결과(`graded`)를 클라이언트가 보낸 `answers` 순서 그대로 만들고,
      `QuizAnswer` 행도 그 순서 그대로 INSERT했다 - `GET /quizzes/{id}`
      가 보여주는 문항 순서와 다르게 답을 제출하는 클라이언트(문항을
      건너뛰며 답하는 UI, 배열 순서를 안 지키는 클라이언트 등)라면
      실제로 마주치는 상황이다. `quiz_attempt_repository.py`의
      `QuizAnswerRepository.list_for_attempt`도 `ORDER BY` 자체가 아예
      없어서(94/116라운드가 다룬 "2차 정렬 키 누락"과는 다른, 정렬
      자체가 없는 별개의 문제), `GET /result`가 다시 조회할 때도 SQL
      표준상 정의되지 않은 순서로 나왔다 - 즉시 응답(`POST /submit`)과
      나중 조회(`GET /result`) 둘 다에서 문항 표시 순서와 답안 순서가
      어긋나 보일 수 있었다.

      두 곳을 고쳤다: (1) `submit_answers`의 채점 루프를 `answers`(클라
      이언트 순서)가 아니라 `questions`(`list_for_quiz`가 이미
      `order_index`로 정렬해서 줌) 순서로 순회하도록 바꿔, 클라이언트가
      보낸 순서와 무관하게 채점 결과·INSERT 순서 모두 문항 순서를
      따르게 했다. (2) `QuizAnswerRepository.list_for_attempt`가
      `QuizQuestion`과 조인해 그 `order_index`로 정렬하도록 고쳐,
      `GET /result`(및 같은 메서드를 쓰는 `_find_recent_duplicate_attempt`
      의 중복 제출 캐시 응답 경로)도 항상 문항 순서로 나오게 했다 -
      리포지토리 레벨에서 한 번 고쳐 두 호출부를 동시에 해결했다.

      `tests/test_quiz.py`에
      `test_submit_answers_out_of_order_returns_result_in_question_order`
      를 추가해, 두 번째 문항을 먼저·첫 번째 문항을 나중에 제출해도
      `POST /submit` 응답과 `GET /result` 조회 둘 다 `answers` 배열이
      실제 문항 순서(첫 번째, 두 번째)로 나오는지 확인했다. `git stash`
      로 `quiz_service.py`/`quiz_attempt_repository.py` 수정만
      되돌리면 정확히 실패(두 응답 모두 문항 순서가 아니라 제출 순서
      그대로 나옴)하는 것까지 확인했다. 전체 450개 테스트 통과, 전체
      커버리지 99%(`quiz_service.py`/`quiz_attempt_repository.py` 둘
      다 100% 포함), `mypy app tests scripts` 클린. 채점 결과(점수/정답
      여부)나 응답 스키마 자체는 그대로고 배열 순서만 바뀐 것이라
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요
      없었다.

## 백로그 (131라운드)

- [x] 155. 데이터 export(`GET /export/me`)가 쓰는 페이지네이션 없는
      `list_all_for_user`/`list_for_user`류 메서드 5개에 `id` 2차 정렬
      기준이 빠져 있던 문제 수정. 94번 라운드가 `list_for_user`(페이지네이션
      있음, LIMIT/OFFSET) 형제 메서드들에는 이미 이 문제(타임스탬프만으로
      정렬하면 값이 같은 행 사이의 순서가 SQL 표준상 정의되지 않음)를
      고쳤는데, export 전용으로 페이지네이션 없이 전체를 가져오는 다섯
      메서드(`StudySessionRepository.list_all_for_user`/
      `InterviewPracticeSessionRepository.list_all_for_user`/
      `QuizRepository.list_all_for_user`/
      `InterviewReviewRepository.list_all_for_user`/
      `QuizAttemptRepository.list_for_user`)는 그 수정에서 빠져 있었다 -
      154라운드의 조사가 후보로 처음 발견해 "페이지네이션이 없어 중복/
      누락 위험은 없지만, 같은 호출이 매번 다른 순서를 반환할 수 있다"고
      낮은 우선순위로 남겨둔 항목을, 이번 라운드에서 다른 더 나은
      후보(세션 삭제 중 동시 메시지/답변 생성이 RAG 색인을 고아로 남기는
      경쟁 상태)를 검토했으나 그건 `send_message`/`stream_message`에
      아직 없는 잠금 규율을 이 코드베이스에서 가장 자주 호출되는 채팅
      경로에 새로 도입해야 하는 더 크고 위험한 변경이라 이번 라운드
      범위로는 보류하고, 안전하고 이미 검증된 패턴을 그대로 반복하는
      이 항목을 대신 골랐다.

      다섯 파일 모두 기존 타임스탬프 정렬 기준 뒤에 `id`를 2차 기준으로
      추가했다(정렬 방향은 각 메서드의 기존 오름차순/내림차순을 그대로
      유지). `tests/test_study.py`/`tests/test_interview_practice.py`/
      `tests/test_quiz.py`/`tests/test_interview_review.py`에는 94라운드가
      페이지네이션 형제 메서드에 쓴 것과 같은 statement-interception
      기법(리포지토리가 세션에 전달하는 실제 SQL의 `ORDER BY` 절에 `id`가
      포함돼 있는지 직접 확인 - 이 동시성은 SQLite로 재현할 수 없어
      68번 라운드와 같은 이유로 이 기법을 쓴다)으로 4개를 추가했고,
      `QuizAttemptRepository.list_for_user`만 이미 같은 파일
      (`tests/test_quiz_submission_dedup.py`)에 있던
      `get_latest_for_quiz`용 "완전히 같은 시각의 시도 두 개를 직접
      생성"하는 더 강한 기법(간접 검증이 아니라 실제 결과 순서를
      확인)을 그대로 재사용했다. `git stash`로 다섯 리포지토리 수정만
      되돌리면 5개 테스트 전부 정확히 실패(`ORDER BY`에 `id`가 없거나,
      먼저 만든 시도가 실제로 먼저 안 나옴)하는 것까지 확인했다. 전체
      455개 테스트 통과, 전체 커버리지 99%(수정한 리포지토리 5개 전부
      100% 유지), `mypy app tests scripts` 클린. `GET /export/me`의
      응답 스키마/필드는 그대로고 배열 순서 결정성만 좋아진 것이라
      `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요
      없었다.

## 백로그 (132라운드)

- [x] 156. CI 워크플로의 mypy 스텝이 `scripts/` 디렉터리를 한 번도 타입
      체크하지 않고 있던 문제 수정. 119번 라운드가
      `scripts/backfill_knowledge_chunks.py`에 새 의존성(PyYAML)을
      추가하면서 겪었던 실제 사고(로컬에서 `mypy app`만 돌려 통과를
      확인했는데, CI가 실제로 돌리는 명령은 그보다 넓어서 로컬에서는
      안 걸리던 오류가 났던 일)를 계기로 "앞으로 CI와 정확히 같은
      `mypy app tests scripts`를 로컬에서도 돌린다"는 검증 습관을 그
      라운드 이후 계속 지켜왔는데, 정작 CI 워크플로
      (`.github/workflows/ci.yml`) 자체는 여전히 `mypy app tests`만
      실행하고 있었다 - `git log`로 이 줄이 9번 라운드 이후 한 번도
      바뀐 적이 없다는 것까지 확인했다. 즉 `scripts/`의 타입 회귀는
      로컬에서 그 습관을 실제로 지켰을 때만 잡히고, CI 자체는 전혀
      못 잡는 사각지대였다 - 113~120라운드가 CI 자체를 집중적으로
      다뤘는데도 놓친, 이번에 새로 발견한 인스턴스다.

      `.github/workflows/ci.yml`의 mypy 스텝을 `mypy app tests scripts`
      로 바꿨다(로컬에서 클린한 것과 동일하게 확인). `tests/
      test_ci_workflow.py`에 `test_ci_type_checks_scripts_directory`를
      추가해 워크플로 파일에 그 정확한 명령 문자열이 있는지 확인했다 -
      113/114라운드가 `docker-compose.yml`/`Caddyfile` 검증 스텝이
      조용히 빠지는 회귀를 막기 위해 이미 같은 파일에 쓴 것과 같은
      텍스트 검증 패턴이다. `git stash`로 `ci.yml` 수정만 되돌리면
      정확히 실패하는 것까지 확인했다. 전체 456개 테스트 통과, 전체
      커버리지 99%, `mypy app tests scripts` 클린(이제 CI가 실제로
      돌리는 것과 정확히 같은 명령). 순수 CI 설정 변경이라 애플리케이션
      코드/API 응답 형태에 영향이 없어 `docs/FRONTEND_INTEGRATION.md`
      갱신도, 마이그레이션도 필요 없었다.

## 백로그 (133라운드)

- [x] 157. 데이터 export(`GET /export/me`)가 쓰는
      `QuizAnswerRepository.list_for_attempts`(복수형)에도 154라운드가
      단수형 `list_for_attempt`(`GET /quizzes/{id}/result`가 씀)에 적용한
      것과 같은 정렬 누락 문제가 남아 있던 것을 발견해 수정. 154라운드는
      `list_for_attempt`가 `ORDER BY` 없이 조회돼(요청 스키마가 문항 순서
      제출을 강제 안 하므로 답안이 사실상 임의 순서로 INSERT됨) 결과 순서가
      SQL 표준상 정의되지 않던 문제를 `QuizQuestion`과 조인해 그
      `order_index`로 정렬하는 방식으로 고쳤는데, 86라운드에서 export의
      N+1을 없애려고 따로 만든 복수형 `list_for_attempts`(여러 시도의
      답안을 한 번에 가져와 파이썬에서 attempt_id별로 묶는 메서드)는
      `attempt_id`로만 정렬해 같은 시도 안 답안 순서 자체는 여전히
      정의되지 않은 채로 남아 있었다 - `GET /quizzes/{id}/result`가
      보여주는 답안 순서와 `GET /export/me`가 보여주는 같은 시도의 답안
      순서가 서로 어긋나 보일 수 있는, 두 뷰 사이의 실제 데이터 불일치
      문제였다.

      `list_for_attempts`도 같은 방식으로 `QuizQuestion`과 조인해
      `(attempt_id, order_index)` 순으로 정렬하도록 고쳤다. 처음에는
      154라운드와 같은 패턴(문항을 뒤바꿔 제출한 뒤 `GET /export/me`의
      실제 응답 순서를 확인)으로 엔드투엔드 회귀 테스트를 작성했는데,
      `git stash`로 수정만 되돌려도 이 테스트가 그대로 통과해버리는
      것을 발견했다 - `submit_answers`가 이미(154라운드 수정으로) 문항
      순서대로 `QuizAnswer` 행을 INSERT하므로, SQLite가 이 정도로 단순한
      쿼리에서는 별도 `ORDER BY`가 없어도 우연히 그 삽입 순서를 그대로
      돌려줘 버그가 있어도 테스트가 통과해버리는 것이었다(68/106라운드와
      같은 성격의 함정). 그래서 `interview_review.py`의 동률 정렬
      테스트들이 이미 쓰는 statement-interception 기법(리포지토리가
      세션에 전달하는 실제 SQL을 가로채, 컴파일된 문에 `JOIN
      quiz_questions`와 `ORDER BY`의 `order_index`가 실제로 있는지 직접
      확인)으로 바꿔 다시 작성했다 - `git stash`로 리포지토리 수정만
      되돌리면 이번엔 정확히 실패(조인/정렬절이 없음)하는 것까지
      확인했다. 처음에 썼다가 버린, 아무것도 증명 못 하는 엔드투엔드
      테스트는 지웠다(잘못된 검증을 남겨두지 않기 위함).

      전체 457개 테스트 통과, 전체 커버리지 99%
      (`quiz_attempt_repository.py` 100% 포함), `mypy app tests scripts`
      클린. `GET /export/me`의 응답 스키마/필드는 그대로고 배열 순서만
      바뀐 것이라 `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도
      필요 없었다.

## 백로그 (134라운드)

- [x] 158. `AccountDeletionRequest.current_password`/`UserUpdateRequest.
      current_password`에 다른 모든 비밀번호 필드와 달리 `max_length`가
      빠져 있던 문제 수정. `SignupRequest.password`/`LoginRequest.
      password`/`GuestUpgradeRequest.password`/`UserUpdateRequest.
      password`는 전부 `max_length=72`가 있는데, 두 `current_password`
      필드만 길이 제한이 전혀 없었다 - 112라운드가 `verify_password()`를
      72바이트 초과 입력에도 예외 없이 안전하게(그냥 불일치로) 처리하도록
      이미 고쳐놔서 크래시 위험은 없지만, 상한이 없으면 터무니없이 긴
      값도 스키마 검증은 그대로 통과해 서비스 계층까지 내려가 "비밀번호가
      틀렸습니다"(401)로 응답한다 - 102라운드가 `RefreshRequest.
      refresh_token`에 상한을 추가한 것과 같은 이유로, 다른 필드들처럼
      422로 일찍 거부하는 게 이 코드베이스의 일관된 관례에 맞다. 148~157
      라운드에 걸친 여러 독립 조사가 이 항목을 두 번 후보로 올렸다가
      매번 더 시급한 다른 항목에 밀려 미뤄져 온 것을, 이번 라운드에서
      다른 더 나은 후보가 없어 드디어 구현했다.

      `app/schemas/user.py`의 두 `current_password: str | None = None`
      필드를 `Field(default=None, max_length=72)`로 바꿨다.
      `tests/test_users.py`에
      `test_update_profile_rejects_oversized_current_password`
      (`PATCH /users/me`)와
      `test_delete_account_rejects_oversized_current_password`
      (`DELETE /users/me`)를 추가해, 73자 `current_password`가 422로
      거부되는지 확인했다. `git stash`로 `app/schemas/user.py` 수정만
      되돌리면 두 테스트 모두 정확히 실패(401로 응답)하는 것까지
      확인했다. 전체 459개 테스트 통과, 전체 커버리지 99%
      (`app/schemas/user.py` 100% 포함), `mypy app tests scripts` 클린.
      정상 범위(72자 이하) 비밀번호 확인 동작은 그대로라 `docs/
      FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (135라운드)

- [x] 159. `MAX_QUIZ_CHOICE_COUNT`에 하한 검증이 없어, 4 미만으로 설정하면
      퀴즈 생성 기능 전체가 시작 시점엔 전혀 티가 안 나는 상태로 계속
      실패(매 요청 502)하던 문제 수정. `quiz_service.py`의
      `_build_quiz_prompt()`는 `MAX_QUIZ_CHOICE_COUNT`와 무관하게 모델에게
      항상 "각 문항은 4개의 보기를 가지고"라고 고정으로 요청한다 - 정상
      동작하는 모델은 매번 보기 4개를 뱉는다는 뜻이다. 그런데 108라운드가
      추가한 이 값(AI 출력 검증용 안전장치, 기본값 8)에는 여태 하한
      검증이 없어서, 운영자가 "문항당 보기 수를 이 값으로 강제한다"고
      오해해 2나 3으로 설정하면(자연스러운 오해다 - 실제로는 검증
      상한일 뿐 요청 개수가 아님), 모델이 시키는 대로 4개를 뱉을
      때마다 `len(q.choices) <= max_quiz_choice_count` 검증에 매번 걸려
      재시도(`_MAX_QUIZ_GENERATION_ATTEMPTS`)까지 전부 소진하고 502로
      끝난다. `Settings()` 생성 자체는 성공해 앱도 정상적으로 뜨므로,
      `JWT_SECRET_KEY` 길이/`LOG_LEVEL`/`ENVIRONMENT`/레이트리밋 문자열/
      토큰 만료 시간(127라운드)/퀴즈 문항 수 기본값(108라운드)처럼 이미
      여러 라운드가 막아온 "Settings 필드 하나가 시작 시점 검증 없이
      조용히 앱을 망가진 상태로 띄우는" 클래스의, 이 파일에 남아있던
      마지막 미검증 숫자 필드였다.

      `app/core/config.py`에 `max_quiz_choice_count`용 `field_validator`
      를 추가해 `< 4`면 거부하도록 했다 - 프롬프트가 실제로 요청하는
      고정 개수(4)와 맞춰, 스키마가 구조적으로 보장하는 최소값(2,
      `_GeneratedQuestion.choices`의 `min_length=2`)이 아니라 이 앱이
      실제로 정상 동작하는 데 필요한 진짜 하한을 검증하도록 했다.
      `tests/test_config.py`에
      `test_settings_accepts_max_quiz_choice_count_of_four_or_more`와
      `test_settings_rejects_max_quiz_choice_count_below_four`
      (0/1/2/3 parametrize)를 추가했다. `git stash`로
      `app/core/config.py` 수정만 되돌리면 4개 케이스 전부 정확히
      실패(`ValidationError`가 안 남)하는 것까지 확인했다. 전체 464개
      테스트 통과, 전체 커버리지 99%(`app/core/config.py` 100% 포함),
      `mypy app tests scripts` 클린. 정상 범위(4 이상) 설정의 동작은
      그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도
      필요 없었다.

## 백로그 (136라운드)

- [x] 160. `MAX_PROMPT_LENGTH`에 하한 검증이 없어, 0 이하로 설정하면 이
      앱의 AI 메시징 기능 전체(`/api/chat`, 학습챗 REST+WS, 면접연습 답변
      제출)가 시작 시점엔 전혀 티가 안 나는 상태로 계속 막히던 문제 수정.
      `ChatRequest`/`StudyMessageCreateRequest`/
      `InterviewPracticeAnswerRequest`의 길이 검증 `field_validator`와
      `routes/study.py`의 WS 스트리밍 경로가 전부 이 값을
      `len(value) > max_length`로 검사하는데, 이 값이 0 이하면
      `min_length=1`을 통과한(=빈 문자열이 아닌) 어떤 메시지든 항상 이
      조건을 만족해 거부된다 - 159라운드가 고친 `MAX_QUIZ_CHOICE_COUNT`
      (퀴즈 생성만 막힘)보다 영향 범위가 더 넓다(메시지를 보내는 모든
      기능이 막힘). `Settings()` 생성 자체는 성공해 앱도 정상적으로 뜨므로,
      이 파일이 이미 여러 라운드에 걸쳐 막아온 "Settings 필드 하나가
      시작 시점 검증 없이 조용히 앱을 망가진 상태로 띄우는" 클래스의,
      159라운드가 "이제 없다"고 여겼던 것과 달리 실제로는 남아있던
      인스턴스였다.

      `app/core/config.py`에 `max_prompt_length`용 `field_validator`를
      추가해(`_validate_token_expiry_is_positive`/
      `_validate_max_quiz_choice_count`와 같은 위치·문체) `<= 0`이면
      거부하도록 했다. `tests/test_config.py`에
      `test_settings_accepts_positive_max_prompt_length`와
      `test_settings_rejects_non_positive_max_prompt_length`(0/-1
      parametrize)를 추가했다. `git stash`로 `app/core/config.py`
      수정만 되돌리면 두 케이스 모두 정확히 실패(`ValidationError`가
      안 남)하는 것까지 확인했다. 전체 467개 테스트 통과, 전체 커버리지
      99%(`app/core/config.py` 100% 포함), `mypy app tests scripts`
      클린. 정상 범위(양수) 설정의 동작은 그대로라 `docs/
      FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

## 백로그 (137라운드)

- [x] 161. `MAX_BODY_SIZE_BYTES`에 양수 검증이 없어, 0 이하로 설정하면
      이 앱의 쓰기 API 사실상 전체(회원가입/로그인/학습챗/퀴즈 제출/
      면접복기 등)가 시작 시점엔 전혀 티가 안 나는 상태로 계속 막히던
      문제 수정. `MaxBodySizeMiddleware`(`core/middleware.py`)는
      `Content-Length` 헤더가 있는 모든 요청에 대해
      `parsed_content_length > self.max_body_size`면 413로 거부한다 -
      이 값이 0이면 본문이 있는(`Content-Length`가 1 이상인) 요청은
      전부 거부되고, 음수라면 본문이 없는(`Content-Length: 0`) 요청까지
      거부된다. 159/160라운드가 고친 `MAX_QUIZ_CHOICE_COUNT`/
      `MAX_PROMPT_LENGTH`보다도 영향 범위가 더 넓다 - 그쪽들은 각각
      퀴즈 생성/메시지 전송 기능만 막았지만, 이건 회원가입/로그인처럼
      메시지가 아닌 요청까지 포함해 본문이 있는 모든 쓰기 요청을 막는다.
      `Settings()` 생성 자체는 성공해 앱도 정상적으로 뜨므로, 이 파일이
      여러 라운드에 걸쳐 막아온 "Settings 필드 하나가 시작 시점 검증
      없이 조용히 앱을 망가진 상태로 띄우는" 클래스의 또 다른 인스턴스
      였다 - 160라운드의 조사가 다음 라운드 후보로 미리 짚어둔 항목을
      그대로 구현했다.

      `app/core/config.py`에 `max_body_size_bytes`용 `field_validator`
      를 추가해(`_validate_max_prompt_length_is_positive`/
      `_validate_max_quiz_choice_count`와 같은 위치·문체) `<= 0`이면
      거부하도록 했다. `tests/test_config.py`에
      `test_settings_accepts_positive_max_body_size_bytes`와
      `test_settings_rejects_non_positive_max_body_size_bytes`(0/-1
      parametrize)를 추가했다. `git stash`로 `app/core/config.py`
      수정만 되돌리면 두 케이스 모두 정확히 실패(`ValidationError`가
      안 남)하는 것까지 확인했다. 전체 470개 테스트 통과, 전체 커버리지
      99%(`app/core/config.py` 100% 포함), `mypy app tests scripts`
      클린. 정상 범위(양수) 설정의 동작은 그대로라 `docs/
      FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도 필요 없었다.

      (이 라운드와 무관하게, 전체 스위트 실행 중
      `app/services/user_service.py:69-71`(`update_profile`의 동시
      이메일 중복 가입을 409로 변환하는 `IntegrityError` 방어 분기)이
      테스트로 전혀 안 걸리고 있는 것을 우연히 발견했다 - 기존에
      "미커버 2줄"로 알려져 있던 `interview_review.py:61`/
      `auth_service.py:115`와 같은 성격의 방어 분기이지만 그동안
      감사에서 누락되어 있었다. 이번 라운드 범위(`MAX_BODY_SIZE_BYTES`)
      와 무관한 별개 파일이라 여기서 손대지 않고, 다음 라운드 조사를
      위한 메모로 남겨둔다.)

## 백로그 (138라운드)

- [x] 162. 161라운드에서 우연히 발견한
      `UserService.update_profile`의 `IntegrityError`→409 방어 분기
      (`user_service.py:67-73`)가 결정론적으로 커버되지 않던 문제 해소.
      실제로는 완전히 테스트가 없던 게 아니라
      `test_concurrent_email_change_to_same_email_yields_clean_conflict_
      not_crash`(파일 기반 SQLite + `asyncio.gather`로 진짜 동시성을
      재현하는 기존 테스트)가 이미 이 분기를 다루고 있었다 - 다만 이
      테스트는 두 동시 요청 중 어느 쪽이 실제로 이 `except IntegrityError`
      분기를 타는지가 진짜 OS 스케줄링에 좌우되는 진짜 경쟁이라, 실행마다
      커버리지가 들쭉날쭉할 수 있는 구조였다(우연히 이 라운드 직전
      전체 스위트 실행에서 걸리지 않아 "미커버"로 보였던 것). 진짜
      동시성 테스트 자체는 여전히 가치 있으므로 그대로 남겨두고, 매
      실행마다 이 분기를 결정론적으로 걸치는 보완 테스트를 별도로
      추가했다.

      `tests/test_users.py`에
      `test_update_profile_converts_concurrent_email_conflict_to_409`
      를 추가했다 - `get_by_email()`이 실제로는 이미 다른 사용자가
      그 이메일로 커밋해둔 상황에서도 "충돌 없음"으로 잘못 답하는
      상황을(`UserRepository.get_by_email`을 직접 패치해) 결정론적으로
      만들어, `commit()` 시점에야 유니크 제약 위반이 드러나는 경로를
      매번 정확히 재현한다. 이 테스트를 작성하는 과정에서 스크립트
      끝에 `asyncio.run(_run())`을 실수로 중복 호출해두는 바람에 같은
      인메모리 DB에 같은 이메일로 두 번째 삽입을 시도해 진짜
      `IntegrityError`가 새어나가는 버그를 겪었다 - 원인을 끝까지
      추적해(단독 스크립트로 같은 로직을 재현해보며 좁혀감) 중복 호출을
      제거하고 나서야 의도한 대로 통과하는 것을 확인했다. 방어 분기
      자체가 실제로 필요한지도, 직접 `except IntegrityError` 블록을
      코드에서 임시로 제거해 이 새 테스트(및 기존 동시성 테스트)가
      정확히 실패(처리되지 않은 `IntegrityError`가 새어나감)하는 것을
      확인한 뒤 복원했다.

      전체 471개 테스트 통과, `app/services/user_service.py` 100%
      커버리지 복원, `mypy app tests scripts` 클린. 순수 테스트
      보강이라 애플리케이션 코드 변경은 없었고(방어 분기 자체는 이미
      올바르게 존재), `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (139라운드)

- [x] 163. WebSocket 스트리밍 라우트(학습챗 `stream_message`, 면접복기
      `stream_create_review`) 두 곳 모두, `HTTPException`이 아닌
      예외가 나면 로그 한 줄 없이, 클라이언트에게 에러 이벤트도 없이
      연결만 뚝 끊기던 문제 해소.

      `app/main.py`의 `@app.exception_handler(Exception)`(모든
      처리되지 않은 예외를 `logger.exception()`으로 로그 남기고 500을
      반환하는 앱의 유일한 안전망)은 실제로는 Starlette의
      `ServerErrorMiddleware`에만 걸리는데, 이 미들웨어는
      `scope["type"] != "http"`이면(즉 websocket이면) 그냥
      통과시키기만 하고 아무 것도 안 한다 - 순정 Starlette 소스를 직접
      확인하고, 임시 테스트로 `RuntimeError`를 실제로 던져 로그 한
      줄도 안 남고 에러 이벤트도 없이 연결만 끊기는 것까지 재현해서
      검증했다. 두 라우트 모두 지금까지는 `except HTTPException`만
      잡고 있었다 - 예상된 실패(AI 서비스 오류, 세션 없음, 잘못된
      JSON, 레이트리밋)는 전부 이미 `HTTPException`으로 변환되어
      들어오므로 기존 테스트는 이 빈틈을 전혀 건드리지 않았다. 실제로는
      DB 커넥션이 순간적으로 끊기거나 임베딩/RAG 쪽에서 예상 못 한
      타입의 예외가 올라오는 경우처럼, 이 두 엔드포인트(앱에서 가장
      AI 연산이 무거운 두 경로)에서 언젠가 실제로 벌어질 수 있는
      시나리오다.

      `app/api/v1/routes/study.py`와
      `app/api/v1/routes/interview_review.py`의 `stream_message`/
      `stream_create_review`에 각각 `except HTTPException` 다음에
      `except Exception` 절을 추가했다 - 모듈 레벨
      `logger = logging.getLogger(__name__)`로 `logger.exception(...)`
      호출해 로그를 남기고, `{"type": "error", "detail": "..."}`
      프레임을 보낸 뒤 `status.WS_1011_INTERNAL_ERROR`로 연결을 닫는다
      (루프를 계속 돌리지 않고 닫는 이유: 부분 flush 도중 실패했을 수
      있어 그 `AsyncSession`의 트랜잭션 상태가 깨끗하다고 보장할 수
      없으므로, 계속 재사용하기보다 연결을 끝내는 쪽이 안전하다).

      `tests/test_study.py`/`tests/test_interview_review.py`에 각각
      `CrashingOllamaService`(`OllamaServiceError`가 아닌
      `RuntimeError`를 던지는 페이크)를 추가하고,
      `test_stream_message_unexpected_exception_sends_error_event_and_logs`/
      `test_stream_create_review_unexpected_exception_sends_error_event_and_logs`를
      새로 작성했다 - 클라이언트가 에러 이벤트를 받는지, `caplog`로
      실제로 로그가 남는지, 그 다음 연결이 끊기는지(`WebSocketDisconnect`)까지
      확인한다. `git stash`로 두 라우트 파일 수정만 되돌리면 두
      테스트 모두 정확히 실패(`RuntimeError`가 그대로 새어나와 테스트
      러너까지 전파됨)하는 것까지 확인했다.

      전체 473개 테스트 통과, `app/api/v1/routes/study.py`/
      `app/api/v1/routes/interview_review.py` 100% 커버리지,
      `mypy app tests scripts` 클린(전체 커버리지 99%, 나머지 미커버
      2줄은 이번 라운드와 무관한 기존 갭). 두 라우트의 정상/기존
      에러 흐름은 그대로라 `docs/FRONTEND_INTEGRATION.md`의 에러 이벤트
      형식(`{"type": "error", "detail": "..."}`)과도 일치하고, DB
      스키마 변경이 없어 마이그레이션도 필요 없었다.

## 백로그 (140라운드)

- [x] 164. `MAX_CONCURRENT_WS_CONNECTIONS`에 양수 검증 추가 - 159~161라운드가
      고친 `MAX_QUIZ_CHOICE_COUNT`/`MAX_PROMPT_LENGTH`/`MAX_BODY_SIZE_BYTES`와
      같은 성격의, "`Settings()` 생성은 성공해 앱이 정상적으로 뜨지만 특정
      기능 전체가 시작 시점엔 티가 안 나게 막히는" 부류의 설정 검증 공백을
      계속 훑다가 발견했다.

      `core/dependencies.py`의 `limit_ws_connections`는
      `_active_ws_connections >= settings.max_concurrent_ws_connections`면
      `accept()` 전에 연결을 거부한다. `_active_ws_connections`는 모듈
      레벨에서 `0`으로 시작하는 카운터라, 이 설정값을 `0`으로 두면(예:
      "아직 예약된 연결 없음"으로 오해, 또는 이 파일의 다른 필드처럼
      "0 이하 = 무제한/비활성"이라는 관례를 착각해 적용) `0 >= 0`이 첫
      연결 시도부터 항상 참이 되어, 학습챗/면접복기 WebSocket 스트리밍
      (139라운드가 예외 처리를 보강한 바로 그 두 경로) 전체가 매번
      `WS_1013_TRY_AGAIN_LATER`로 거부된다. REST 엔드포인트는 이 검사를
      거치지 않아 영향이 없어, 겉보기엔 앱 전체가 멀쩡해 보인다는 점도
      기존에 고친 항목들과 같다.

      `app/core/config.py`에 `_validate_max_concurrent_ws_connections_is_
      positive` field_validator를 추가했다(`value < 1`이면 거부, 기존
      필드들과 동일한 위치/스타일). `tests/test_config.py`에
      `test_settings_accepts_positive_max_concurrent_ws_connections`와
      `test_settings_rejects_non_positive_max_concurrent_ws_connections`
      (0/-1 parametrize)를 추가했다. `git stash`로 `app/core/config.py`
      수정만 되돌리면 두 케이스 모두 정확히 실패(`ValidationError`가
      안 남)하는 것까지 확인했다.

      전체 476개 테스트 통과, 전체 커버리지 99%(`app/core/config.py`
      100% 포함), `mypy app tests scripts` 클린. 정상 범위(양수) 설정의
      동작은 그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도, 마이그레이션도
      필요 없었다.

## 백로그 (141라운드)

- [x] 165. `MAX_REVIEW_CONTENT_LENGTH`에 양수 검증 추가 - 140라운드
      조사에서 후보로만 언급되고 구현되지 않았던 항목을 이어받았다.
      159~164라운드와 같은 성격의 설정 검증 공백이다.

      `InterviewReviewCreateRequest`/`InterviewReviewUpdateRequest`
      (schemas/interview_review.py)의 `validate_content_length`
      field_validator가 이 값을 `len(value) > max_length`로 검사한다.
      이 값이 0 이하면 `min_length=1`을 통과한(=빈 문자열이 아닌) 어떤
      면접복기 내용도 항상 이 조건을 만족해 거부된다 - `POST
      /interview-reviews`(생성)와 `PATCH /interview-reviews/{id}`
      (content를 포함한 수정) 전부가 시작 시점에는 전혀 티가 안 나는
      상태로 계속 막히게 된다. `Settings()` 생성 자체는 성공해 앱도
      정상적으로 뜨므로, 160라운드가 고친 `MAX_PROMPT_LENGTH`와 정확히
      같은 형태의 버그이지만 영향 범위는 면접복기 기능으로 한정된다.

      `app/core/config.py`에
      `_validate_max_review_content_length_is_positive` field_validator를
      추가했다(`value <= 0`이면 거부, 기존 필드들과 동일한 위치/스타일).
      `tests/test_config.py`에
      `test_settings_accepts_positive_max_review_content_length`와
      `test_settings_rejects_non_positive_max_review_content_length`
      (0/-1 parametrize)를 추가했다. `git stash`로
      `app/core/config.py` 수정만 되돌리면 두 케이스 모두 정확히
      실패(`ValidationError`가 안 남)하는 것까지 확인했다.

      전체 479개 테스트 통과, 전체 커버리지 99%(`app/core/config.py`
      100% 포함), `mypy app tests scripts` 클린. 정상 범위(양수) 설정의
      동작은 그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

      (140라운드 조사가 함께 발견한 `MAX_QUIZ_SOURCE_LENGTH <= 0`은
      성격이 다르다 - 스키마 검증 경로는 이번 라운드와 같은 "항상
      거부" 버그지만, `quiz_service.py`의 세션 소스 truncate 경로는
      `source_text[-0:]`가 파이썬 슬라이싱 특성상 `-0 == 0`이라
      전체 문자열을 그대로 반환해버려 truncate 안전장치 자체가
      조용히 무력화되는 별개의 버그다. "0을 거부할지 무제한으로
      취급할지"가 설계 판단이 필요해(이 파일에 `max_chat_history_
      messages`처럼 "0 이하 = 특수 모드"로 문서화된 필드가 있어
      선례가 갈릴 수 있음) 이번 라운드 범위에는 넣지 않고, 다음
      라운드를 위한 메모로 남겨둔다.)

## 백로그 (142라운드)

- [x] 166. `MAX_QUIZ_SOURCE_LENGTH`에 양수 검증 추가 - 141라운드가
      설계 판단이 필요하다는 이유로 메모만 남기고 미룬 항목을
      이어받아 판단하고 구현했다.

      이 값은 서로 다른 두 곳에서 서로 다른 방식으로 소비되는데, 둘
      다 0 이하에서 깨진다. (1) `QuizCreateRequest`(schemas/quiz.py)의
      직접 붙여넣기 경로는 `len(source_text) > max_length`로 검사한다 -
      0 이하면 `min_length=1`을 통과한(=빈 문자열이 아닌) 어떤
      `source_text`도 항상 이 조건을 만족해 거부된다(`MAX_PROMPT_
      LENGTH`/`MAX_REVIEW_CONTENT_LENGTH`와 같은 "항상 거부" 형태).
      (2) `quiz_service.py`의 학습 세션 소스 경로는 상한을 넘으면
      `source_text[-max_length:]`로 뒤쪽(최근)만 남기는데, 0에서는
      파이썬 슬라이싱 특성상 `-0 == 0`이라 `source_text[-0:]`가
      `source_text[0:]`(전체 문자열)이 되어버려 잘라내기는커녕
      아무것도 안 자른 것과 같아진다 - `git diff` 없이 파이썬
      REPL에서 직접 재현해(`"abc"[-0:]` → `"abc"`, `"abc"[-3:]` →
      `"abc"`이지만 `[-2:]` → `"bc"`) 확인했다. (1)과 달리 요청이
      거부되지 않고 그냥 넘어가버려서(Ollama 호출 지연/타임아웃/
      컨텍스트 윈도우 초과 방지용 안전장치가 조용히 무력화됨) 더
      알아채기 어렵다.

      설계 판단: 이 파일에는 `max_chat_history_messages`처럼 "0
      이하 = 특수 모드"가 명시적으로 문서화된 필드도 있지만,
      `max_quiz_source_length`는 그런 의미가 문서화되어 있지 않고
      순수하게 AI 입력 길이를 제한하는 안전장치라는 점에서
      `MAX_PROMPT_LENGTH`와 같은 성격이다(둘 다 두 소비처 중
      어느 쪽도 "0 = 무제한"을 기대하지 않고, 둘 다 AI 호출
      지연/타임아웃/컨텍스트 윈도우 초과를 막는 게 유일한 목적).
      "무제한"으로 특별 취급하지 않고, 같은 이유로 시작 시점에
      미리 거부하기로 했다.

      `app/core/config.py`에
      `_validate_max_quiz_source_length_is_positive` field_validator를
      추가했다(`value <= 0`이면 거부, 두 소비처의 서로 다른 실패
      양상을 모두 docstring에 남김). `tests/test_config.py`에
      `test_settings_accepts_positive_max_quiz_source_length`와
      `test_settings_rejects_non_positive_max_quiz_source_length`
      (0/-1 parametrize)를 추가했다. `git stash`로
      `app/core/config.py` 수정만 되돌리면 두 케이스 모두 정확히
      실패(`ValidationError`가 안 남)하는 것까지 확인했다.

      전체 482개 테스트 통과, 전체 커버리지 99%(`app/core/config.py`
      100% 포함), `mypy app tests scripts` 클린. 정상 범위(양수) 설정의
      동작은 그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

## 백로그 (143라운드)

- [x] 167. `InterviewReviewService.update_review()`가 RAG 재색인 실패 시
      방금 저장한 수정 내용을 통째로 잃어버리고 크래시까지 하던 버그
      해소 - 지난 6라운드 연속 `config.py` 숫자 필드 검증만 다뤄서
      이번엔 다른 영역을 조사했고, RAG 색인 파이프라인과 최근 추가된
      기능들을 다시 훑다가 발견했다.

      `RagService.index_content()`는 자신의 docstring에 명시된 전제가
      있다 - "본 기능이 이미 커밋된 뒤" 마지막 단계로 호출되어야 하며,
      임베딩 호출뿐 아니라 예상 못 한 DB 오류까지 조용히 삼키기 위해
      실패 시 `session.rollback()`을 부른다. `create_review`/
      `stream_create_review`(같은 파일)와 `interview_practice_service.
      submit_answer`(동일하게 `get_for_user_locked`를 쓰는 자매 메서드)
      모두 이 전제를 지켜 커밋을 먼저 끝낸 뒤 `index_content`를 부르는데,
      `update_review`만 유일하게 거꾸로 되어 있었다 - `content`/
      `ai_feedback` 수정을 아직 커밋하지 않은 채로 `index_content`를
      먼저 부르고 있었다("같은 복기에 대한 거의 동시 수정을 직렬화하는
      FOR UPDATE 잠금을 재색인까지 커버하려는" 의도로 보인다).

      그 결과 `index_content` 내부(`delete_for_source`나 임베딩 생성 이후
      경로)에서 예상 못 한 예외가 나면, 그 메서드가 부르는
      `rollback()`이 같은 트랜잭션이라 아직 커밋 안 된 `content`/
      `ai_feedback` 수정까지 통째로 되돌려버린다 - 사용자는 성공한 줄
      알지만 방금 쓴 수정 내용이 조용히 사라지고, 그 뒤 만료된
      `review` 객체를 반환/직렬화하려다 `MissingGreenlet`까지 발생해
      `PATCH /interview-reviews/{id}`가 예외 처리 안 된 500으로 끝난다.
      `KnowledgeChunkRepository.delete_for_source`를 패치해 재색인
      도중 DB 오류를 재현하는 것으로 직접 확인했다(수정 전 코드에서
      정확히 `MissingGreenlet`이 재현됨).

      `app/services/interview_review_service.py`의 `update_review`를
      다른 4개 호출부와 같은 순서(커밋 → 재색인)로 바꿨다. 대신 FOR
      UPDATE 잠금은 커밋 시점에 풀리므로, 아주 드문 "같은 복기를 정말
      동시에 두 번 수정"하는 경우 재색인 단계끼리는 더 이상
      직렬화되지 않아 이론적으로 `knowledge_chunks`에 중복 행이 생길
      수 있다 - 하지만 다음 수정의 `delete_for_source`가 그 중복까지
      지우고 다시 만들어 자연히 복구되므로, 매 수정마다(동시성과 무관)
      사용자의 실제 수정 내용을 통째로 잃어버릴 수 있던 기존 버그보다
      훨씬 가벼운 대가라고 판단했다. `app/repositories/interview_review_
      repository.py`의 `get_for_user_locked()` docstring도 이 잠금이
      더 이상 재색인을 커버하지 않는다는 사실에 맞게 갱신했다.

      `tests/test_interview_review.py`에
      `test_update_review_persists_content_edit_even_if_rag_reindex_fails`
      를 추가했다 - `KnowledgeChunkRepository.delete_for_source`를 패치해
      재색인 도중 DB 오류를 재현하고, (1) 예외 없이 정상 반환되는지,
      (2) 별도 세션으로 다시 조회했을 때도 수정된 content가 실제로
      커밋되어 있는지 확인한다. `git stash`로 서비스/저장소 파일
      수정만 되돌리면 정확히 진단한 대로 `MissingGreenlet`이 나며
      실패하는 것까지 확인했다.

      전체 483개 테스트 통과,
      `app/services/interview_review_service.py`/`app/repositories/
      interview_review_repository.py` 100% 커버리지, `mypy app tests
      scripts` 클린. `PATCH /interview-reviews/{id}`의 정상 응답
      형식은 그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도, DB 스키마
      변경이 없어 마이그레이션도 필요 없었다.

## 백로그 (144라운드)

- [x] 168. `StudyService.send_message`/`stream_message`가 첫 번째
      INSERT(user_message)에서도 81라운드가 이미 두 번째 INSERT
      (assistant_message)에 대해 고친 것과 같은 종류의 경쟁 상태에
      노출돼 있던 문제 해소 - 143라운드가 고친 `index_content`/
      `forget_content` 커밋 순서 버그를 계기로, "잠금이나 커밋 순서에
      의존하는 다른 호출부도 같은 함정이 있는지" 전수 재감사를 했고
      (`index_content`/`forget_content` 호출부는 전부 정상이었음),
      그 과정에서 이 별개의 오래된 경쟁 상태를 새로 발견했다.

      `send_message`/`stream_message`는 `get_for_user()`로 세션
      존재를 확인한 뒤 `list_recent_for_session()` 조회를 한 번 더
      거쳐서야 `user_message`를 만드는데, 이 좁은 틈에도 다른 요청이
      같은 세션을 지워버리면(`StudyMessage.session_id`가
      `nullable=False` FK) 이 INSERT가 `IntegrityError`로 실패한다.
      81라운드는 그 뒤에 있는 (Ollama 호출까지 거치는 훨씬 넓은
      창의) `assistant_message` INSERT에는 이미 `try/except
      IntegrityError` 방어를 달아뒀지만, 20~30줄 앞의 이 더 이른
      INSERT는 같은 함수 안인데도 그 처리가 빠져 있었다 - 잡히지
      않으면 REST 경로는 전역 예외 핸들러가 없어(main.py는
      `HTTPException`/`RequestValidationError`만 등록) 그대로
      Starlette 기본 500으로 새어나가 이 앱의 균일한 에러 응답 형식이
      깨지고, WebSocket 경로는 139라운드가 추가한 `except Exception`
      에 걸려 "처리되지 않은 예외"로 잘못 로깅되며 정상적인 404
      대신 뭉뚱그린 에러로 연결이 강제 종료된다.
      `StudyMessageRepository.list_recent_for_session`을 패치해
      반환 직전 별도 세션에서 세션을 지우도록 만드는 것으로 직접
      재현해 확인했다.

      `app/services/study_service.py`의 `send_message`/
      `stream_message` 양쪽 모두, 첫 번째 `user_message` 생성+커밋을
      `assistant_message`와 같은 `try/except IntegrityError:
      rollback() + raise _SESSION_NOT_FOUND` 패턴으로 감쌌다.

      `tests/test_study_message_session_deleted_race.py`(81라운드가
      만든 기존 경쟁 테스트 파일)에
      `test_send_message_returns_404_when_session_deleted_before_first_message_insert`
      와 그 스트리밍 버전을 추가했다 - 기존 두 테스트와 같은 패턴
      (가짜 서비스/저장소 메서드가 응답 직전 별도 세션에서 실제로
      세션을 지움)을 재사용하되, 주입 지점만 Ollama 호출 대신
      `list_recent_for_session` 반환 직후로 옮겼다. `git stash`로
      `app/services/study_service.py` 수정만 되돌리면 두 테스트 모두
      정확히 `IntegrityError`(404로 변환되지 않은 원본 예외)로
      실패하는 것까지 확인했다.

      전체 485개 테스트 통과, `app/services/study_service.py` 100%
      커버리지, `mypy app tests scripts` 클린. 두 엔드포인트의 정상
      응답/기존 에러 형식은 그대로라 `docs/FRONTEND_INTEGRATION.md`
      갱신도, DB 스키마 변경이 없어 마이그레이션도 필요 없었다.

## 백로그 (145라운드)

- [x] 169. `AuthService.login()`/`refresh()`가 계정 삭제 경쟁에 노출돼
      있던 문제 해소 - 143/144라운드가 발견한 "check-then-act 사이에
      참조 대상이 지워지면 나중 INSERT가 IntegrityError로 새어나간다"
      버그 클래스를 이 서비스에도 전수 재감사하다가 찾았다(quiz_service/
      interview_practice_service/interview_review_service는 이미 전부
      `get_for_user_locked`나 `try/except IntegrityError`로 방어돼
      있음을 다시 읽어 확인했다).

      `UserService.delete_account()`(비교적 최근에 추가된 기능)로 계정을
      완전히 지우면 `RefreshToken.user_id`가 `nullable=False, ondelete=
      CASCADE` FK라 그 계정의 refresh_token도 함께 사라진다. `login()`은
      `get_by_email()` 확인(과 그 뒤 bcrypt 비교로 늘어난 시간차) 사이에,
      `refresh()`는 `get_by_id()` 확인 뒤 `_issue_tokens()`가 새 토큰을
      `INSERT`하기 전에, 다른 요청(같은 계정의 다른 탭/기기에서 온 계정
      삭제)이 이 계정을 지워버리면 그 INSERT가 `IntegrityError`로
      실패한다 - 잡지 않으면 로그인/토큰 갱신이라는 이 앱에서 가장 자주
      타는 경로가 그대로 처리되지 않은 예외(500)로 새어나간다.

      `app/services/auth_service.py`의 `login()`/`refresh()` 양쪽 모두
      `_issue_tokens()` 호출+커밋을 `try/except IntegrityError:
      rollback() + raise 401`로 감쌌다(`signup()`이 이미 같은 패턴을
      쓰고 있었음). `refresh()`의 경우 `rollback()`이 그 직전
      `revoke_if_active()`의 폐기(UPDATE)까지 함께 되돌리는데, 이는
      의도한 동작이다 - 새 토큰을 발급 못 할 거면 옛 토큰을 헛되이
      태우지 않는 게 맞다.

      `tests/test_auth.py`에 `test_login_returns_401_when_account_
      deleted_during_login`과 `test_refresh_returns_401_when_account_
      deleted_during_refresh`를 추가했다 - 기존
      `test_concurrent_refresh_of_same_token_is_detected_and_revokes_
      all_sessions`(129라운드 이후 이 파일에 이미 있던, 저장소 메서드를
      서브클래싱해 `auth_service_module`에 monkeypatch하는 패턴)와
      144라운드의 "별도 세션에서 실제로 지운다" 기법을 조합해, 각각
      `get_by_email`/`revoke_if_active`가 반환하기 직전 별도 세션에서
      계정을 실제로 지우도록 만들어 재현했다. `git stash`로
      `app/services/auth_service.py` 수정만 되돌리면 두 테스트 모두
      정확히 `IntegrityError`(FOREIGN KEY constraint failed)로
      실패하는 것까지 확인했다.

      조사 과정에서 `refresh()`의 `if user is None: raise
      _INVALID_REFRESH_TOKEN`(더 이른 타이밍 - `get_by_id()` 자체가
      `None`을 반환하는 경우, CASCADE로 refresh_token row 자체가
      이미 함께 지워진 뒤라 이쪽은 원래도 올바르게 처리되고 있었음)
      분기가 오래 전부터 테스트로 커버되지 않고 있던 것도 함께
      발견해서, 같은 조사의 연장으로 `test_refresh_returns_401_when_
      account_deleted_before_user_lookup`을 추가해 메웠다(애플리케이션
      코드 변경 없이 순수 테스트 보강 - `git stash`로 확인해도 이
      테스트는 수정 전/후 동일하게 통과함).

      전체 488개 테스트 통과, `app/services/auth_service.py` 100%
      커버리지(이번 라운드가 우연히 143/144라운드 이전부터 있던
      미커버 갭까지 메워, 전체 미커버 라인이 2개에서 1개로 줄었다),
      `mypy app tests scripts` 클린. `/auth/login`/`/auth/refresh`의
      정상 응답 형식은 그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      DB 스키마 변경이 없어 마이그레이션도 필요 없었다.

## 백로그 (146라운드)

- [x] 170. `InterviewPracticeService.create_session()`/
      `InterviewReviewService.create_review()`/`stream_create_review()`가
      145라운드가 고친 것과 같은 종류의 "계정 삭제 경쟁"에 노출돼
      있던 문제 해소 - 145라운드 조사가 남긴 구체적인 후속 단서(같은
      취약점이 AI 생성이 무거운 다른 생성 경로에도 있을 수 있다는
      추정)를 직접 코드를 다시 읽어 검증한 뒤 구현했다.

      두 서비스 모두 `IntegrityError`를 아예 import조차 안 하고
      있었다 - `create_session()`은 RAG 조회 + Ollama `generate()`
      호출을, `create_review()`/`stream_create_review()`는 Ollama
      `chat()`/`chat_stream()` 호출을 거쳐서야 각각
      `InterviewPracticeSession`/`InterviewReview`를 만드는데
      (둘 다 `user_id`가 `nullable=False, ondelete=CASCADE` FK), 그
      사이 다른 요청(같은 계정의 다른 탭/기기에서 온
      `UserService.delete_account()`)이 이 계정을 지워버리면 그
      INSERT가 `IntegrityError`로 실패한다 - 145라운드가 이미 같은
      계정으로 실제 재현한 것과 동일한 시나리오다. 잡지 않으면 REST는
      처리되지 않은 예외(500)로, WS(`stream_create_review`)는 139라운드가
      추가한 `except Exception`에 걸려 "처리되지 않은 예외"로 잘못
      로깅되며 뭉뚱그린 에러 메시지로 응답한다.

      `app/services/interview_practice_service.py`/`app/services/
      interview_review_service.py` 양쪽에 `IntegrityError` import와
      `_ACCOUNT_GONE`(401,
      `{"code": "invalid_token", "message": "Could not validate credentials"}`
      - `core/dependencies.py`의 `get_current_user`가 "존재하지 않는
      사용자"에 이미 쓰는 것과 같은 코드/메시지이자
      `docs/FRONTEND_INTEGRATION.md`에 이미 문서화된 코드라 재사용함)를
      추가하고, 세 메서드 각각의 row 생성+커밋을 `try/except
      IntegrityError: rollback() + raise _ACCOUNT_GONE`으로 감쌌다.

      `tests/test_interview_practice.py`에
      `test_create_session_returns_401_when_account_deleted_during_generation`을,
      `tests/test_interview_review.py`에
      `test_create_review_returns_401_when_account_deleted_during_generation`
      과 그 스트리밍 버전을 추가했다 - 가짜 Ollama 서비스가 응답을
      반환하기 "직전" 별도 세션에서 그 계정을 실제로 지우도록 만들어
      재현한다(143~145라운드가 확립한 패턴 그대로). `git stash`로
      두 서비스 파일 수정만 되돌리면 세 테스트 모두 정확히
      `IntegrityError`(FOREIGN KEY constraint failed)로 실패하는
      것까지 확인했다.

      전체 491개 테스트 통과, `app/services/interview_practice_
      service.py`/`app/services/interview_review_service.py` 100%
      커버리지, `mypy app tests scripts` 클린. 세 엔드포인트의 정상
      응답/기존 에러 형식은 그대로라 `docs/FRONTEND_INTEGRATION.md`
      갱신도, DB 스키마 변경이 없어 마이그레이션도 필요 없었다.

## 백로그 (147라운드)

- [x] 171. `StudyService.create_session()`도 143~146라운드가 고친 것과
      같은 "계정 삭제 경쟁"에 노출돼 있던 문제 해소 - 4라운드째 이어온
      이 취약점 계열이 이제 실제로 소진됐는지 전수 재점검하다가 발견한
      마지막 한 곳이다.

      점검 결과 대부분은 이미 안전했다: `quiz_service.submit_answers`/
      `interview_practice_service.submit_answer`/`complete_session`은
      `get_for_user_locked`(`SELECT ... FOR UPDATE`)로 부모 행을 잠그고
      있어, Postgres에서 `ON DELETE CASCADE`가 실제로는 그 잠긴 행을
      지우는 `DELETE`이므로 우리 트랜잭션이 커밋할 때까지 막혀
      경쟁이 성립하지 않는다(이번에 처음 명시적으로 확인한 사실).
      `rag_service.index_content`는 원래도 실패를 통째로 삼키도록
      설계돼 있어 무관하다. `user_service`의 `update_profile`/
      `upgrade_guest`는 이미 보호돼 있다.

      다만 `create_session()`만은 `IntegrityError`를 전혀 처리하지
      않고 있었다 - `StudySession.user_id`는 `nullable=False,
      ondelete=CASCADE` FK인데, `get_current_user` 인증 확인과 이
      INSERT 사이(다른 create류 메서드들과 달리 사이에 AI 호출이 없어
      매우 좁은 창)에 다른 요청이 `delete_account()`로 계정을 지우면
      IntegrityError가 새어나간다. 이 파일의 형제 메서드(`send_message`/
      `stream_message`의 `user_message` INSERT, 144라운드)와
      `signup()`(그 자체로도 bcrypt 해싱만큼 좁은 창을 이미 방어 중)이
      이미 지키고 있는 것과 같은 일관성을 위해, 창이 좁다는 이유로
      건너뛰지 않고 막았다.

      `app/services/study_service.py`에 146라운드와 동일한
      `_ACCOUNT_GONE`(401,
      `{"code": "invalid_token", "message": "Could not validate credentials"}`)
      상수를 추가하고, `create_session()`의 생성+커밋을 `try/except
      IntegrityError: rollback() + raise _ACCOUNT_GONE`으로 감쌌다.

      `tests/test_study.py`에
      `test_create_session_returns_401_when_account_deleted_during_creation`
      을 추가했다 - 이 메서드는 AI 호출이 없어 기존 테스트들의 "가짜
      Ollama가 응답 직전에 계정을 지운다" 기법을 못 쓰므로,
      `StudySessionRepository.create`를 직접 패치해 실제 INSERT
      호출 "직전" 별도 세션에서 계정을 지우도록 만들어 이 좁은
      타이밍을 결정적으로 재현했다. `git stash`로
      `app/services/study_service.py` 수정만 되돌리면 정확히
      `IntegrityError`(FOREIGN KEY constraint failed)로 실패하는
      것까지 확인했다.

      전체 492개 테스트 통과, `app/services/study_service.py` 100%
      커버리지, `mypy app tests scripts` 클린. `POST /study/sessions`의
      정상 응답/기존 에러 형식은 그대로라 `docs/FRONTEND_INTEGRATION.md`
      갱신도, DB 스키마 변경이 없어 마이그레이션도 필요 없었다.

      이것으로 143라운드에서 시작된 "check-then-act 중 참조 대상이
      동시에 지워지면 나중 INSERT가 처리되지 않은 예외로 새어나간다"
      취약점 계열은 전수 재점검을 통해 실질적으로 소진됐다고 판단한다
      - 다음 라운드부터는 다른 영역을 조사한다.

## 백로그 (148라운드)

- [x] 172. `InterviewPracticeService.create_session()`이 AI가 뱉은 첫
      질문이 공백뿐이어도 그대로 세션의 첫 턴으로 저장해버리던 문제
      해소 - 지시대로 계정 삭제 경쟁 계열을 벗어나 다른 영역을 조사한
      결과, 152라운드가 고친 것과 판박이인 증상을 그 라운드가 놓친
      한 곳에서 찾았다.

      `OllamaService.generate()`(JSON 스키마를 강제하지 않는 자유 텍스트
      생성)는 응답 본문에 `response` 키가 없거나 모델이 빈/공백 텍스트만
      내보내도 `OllamaServiceError`를 던지지 않고 그냥 빈 문자열을
      돌려준다. `create_session()`은 이 반환값을 검증/재시도 없이 곧바로
      `InterviewPracticeTurn.question`(order_index=0, 세션의 *첫* 턴)으로
      저장하고 있었다 - 152라운드가 `_generate_feedback_and_next_question`의
      `next_question`에 이미 고친 것과 완전히 같은 증상이지만, 그 라운드는
      스스로 "`generate_json()`을 쓰는 두 호출 지점"으로 범위를 명시했고
      `create_session`은 `generate()`(JSON 아님)를 쓰는 별개 호출부라
      그 범위 밖에 있었다. 영향은 오히려 더 크다 - 한 턴 답한 뒤가 아니라
      세션이 시작부터 빈 질문으로 조용히 멈춘다.

      `app/services/interview_practice_service.py`에
      `_generate_first_question()`을 새로 추가해(기존
      `_MAX_FEEDBACK_GENERATION_ATTEMPTS = 2`를 재사용) `_generate_feedback_
      and_next_question`과 같은 형태로 재시도+공백 검증을 하도록 하고,
      `create_session()`이 이를 쓰도록 바꿨다.

      `tests/test_interview_practice.py`에
      `AlwaysBlankFirstQuestionOllamaService`(기존
      `AlwaysBlankNextQuestionOllamaService`와 같은 패턴)와
      `test_create_session_returns_502_when_first_question_is_blank`를
      추가했다 - 재시도 2회를 소진한 뒤 502로 실패 처리되는지, `generate()`가
      정확히 2번 불렸는지 확인한다. `git stash`로
      `app/services/interview_practice_service.py` 수정만 되돌리면 이
      테스트가 정확히 실패(201로 성공 처리되며 빈 질문이 그대로 저장됨)
      하는 것까지 확인했다.

      전체 493개 테스트 통과, `app/services/interview_practice_service.py`
      100% 커버리지, `mypy app tests scripts` 클린. `POST /interview/
      practice-sessions`의 정상 응답 형식은 그대로라(실패 시에만 502로
      바뀜, 이미 문서화된 코드) `docs/FRONTEND_INTEGRATION.md` 갱신도,
      DB 스키마 변경이 없어 마이그레이션도 필요 없었다.

      (조사 중 같은 성격의 "공백 텍스트가 검증 없이 그대로 저장됨" 패턴이
      `complete_session`의 최종 피드백(`interview_practice_service.py`)과
      `interview_review_service._generate_feedback`(면접복기 생성/수정)
      에도 남아있는 것을 발견했다 - 다만 이들은 이미 성공한 상호작용에
      부가되는 정보성 텍스트라 다음 단계를 막는 차단 요소가 아니어서
      (study_service의 채팅 답변처럼 지금까지 감수해온 위험과 비슷한
      성격), 이번 라운드 범위에는 넣지 않고 다음 라운드를 위한 메모로
      남겨둔다.)

## 백로그 (149라운드)

- [x] 173. 148라운드가 메모로 남긴 후보 셋(`submit_answer`의 마지막
      문항 피드백, `complete_session`의 총평, `interview_review_
      service._generate_feedback`) 중 두 곳을 재조사해 실제로
      고쳤다 - "이미 성공한 상호작용에 부가되는 정보성 텍스트"라는
      148라운드의 판단이 맞는지 회수 가능성(recoverability) 관점에서
      다시 검증했다.

      `OllamaService.chat()`도 `generate()`와 같은 이유로 응답에
      `message.content`가 없거나 모델이 빈 텍스트만 내보내도 예외 없이
      빈 문자열을 돌려준다(`ollama_service.py:44-55`, 직접 확인). 세
      곳 모두 이 위험에 노출돼 있었지만, 회수 가능성은 서로 달랐다:
      - `interview_review_service._generate_feedback`(면접복기
        `ai_feedback`)은 `update_review()`가 content가 바뀔 때마다
        다시 생성하는 정상 경로가 이미 있어, 사용자가 (무의미한 수정
        하나로도) 스스로 재생성할 수 있다 - 148라운드의 판단이 맞아
        이번에도 그대로 둔다.
      - `submit_answer`의 마지막 문항 피드백은
        `mark_answered_if_pending()`의 `WHERE answer IS NULL` CAS로
        한 번만 기록되는 단발성 UPDATE라 재제출 엔드포인트가 없고,
        `complete_session`의 총평은 기록과 동시에 `status`를
        `completed`로 바꾸는데 `complete_session` 자신을 포함해 그
        상태를 다시 건드리는 경로가 전혀 없다 - 둘 다 "정보성"이
        아니라 한 번 빈 채로 굳으면 사용자도 시스템도 영원히 되돌릴
        방법이 없는 종료 상태였다. 148/152라운드가 이미 확립한
        재시도+공백 검증 기준(recoverability가 없으면 고친다)에
        따라 이 둘은 판단을 뒤집어 고쳤다.

      `app/services/interview_practice_service.py`에
      `_generate_feedback_text()`를 새로 추가해(기존
      `_MAX_FEEDBACK_GENERATION_ATTEMPTS = 2`를 재사용) `_generate_first_
      question`/`_generate_feedback_and_next_question`과 같은 형태로
      재시도+공백 검증을 하도록 하고, `submit_answer`의 마지막 문항
      분기와 `complete_session` 양쪽이 이를 쓰도록 바꿨다.

      `tests/test_interview_practice.py`에
      `AlwaysBlankChatOllamaService`(기존 `AlwaysBlank*` 패턴)와
      `test_submit_answer_at_final_turn_returns_502_when_feedback_is_blank`,
      `test_complete_session_returns_502_when_overall_feedback_is_blank`를
      추가했다 - 재시도 2회를 소진한 뒤 502로 실패 처리되는지, 그리고
      회수 가능성이 실제로 보존되는지(전자는 해당 턴이 여전히
      미답변으로 남아 나중에 다시 제출 가능함을, 후자는 세션이 여전히
      `in_progress`로 남아 나중에 다시 종료 시도 가능함을 확인)까지
      검증한다. `git stash`로 `app/services/interview_practice_
      service.py` 수정만 되돌리면 두 테스트 모두 정확히 실패(200으로
      성공 처리되며 빈 피드백/총평이 그대로 저장됨)하는 것까지
      확인했다.

      전체 495개 테스트 통과, `app/services/interview_practice_
      service.py` 100% 커버리지, `mypy app tests scripts` 클린. 두
      엔드포인트의 정상 응답 형식은 그대로라(실패 시에만 이미
      문서화된 502로 바뀜) `docs/FRONTEND_INTEGRATION.md` 갱신도, DB
      스키마 변경이 없어 마이그레이션도 필요 없었다.

## 백로그 (150라운드)

- [x] 174. `OllamaService`의 모든 메서드(`generate`/`chat`/`chat_stream`/
      `embed`/`list_models`/`generate_json`)가 Ollama 응답의 값이
      "키 자체가 없음"이 아니라 "키는 있는데 값이 명시적 JSON
      `null`"인 경우를 놓치고 있던 문제 해소 - 152/172/173라운드가
      쌓아온 "AI가 빈 텍스트를 뱉어도 예외 없이 조용히 넘어간다"는
      전제를 한 단계 아래(HTTP 응답 파싱 자체)에서 다시 점검하다가
      발견했다.

      `dict.get(key, default)`는 key가 아예 없을 때만 default를 쓴다 -
      `{"response": null}`처럼 key는 있는데 값이 JSON `null`이면 그대로
      `None`이 반환된다(`response.json().get("response", "")` 같은
      패턴이 이 파일의 6곳 전부에 있었음). 이 서비스의 모든 메서드는
      반환 타입을 `str`/`list`로 선언해뒀고, 152/172/173라운드가 그
      선언을 믿고 만든 재시도+공백 검증 로직(`.strip()`)들은 전부
      "항상 str이 온다"는 전제 위에 있다 - `None`이 새어나가면
      `AttributeError`가 재시도 없이 바로 터진다. 직접 재현해 확인:
      `generate()`가 `{"response": None}`을 받으면 `None`을 반환하고,
      호출부의 `.strip()`이 곧바로 `AttributeError`로 죽는다.

      영향은 호출부마다 달랐다 - `interview_practice_service.py`의 세
      재시도 헬퍼는 재시도 없이 바로 처리되지 않은 예외(500)로 죽고(502가
      아님), `study_service.py`의 `send_message`/`stream_message`는
      `reply=None`이 `StudyMessage.content`(`nullable=False`)에 그대로
      들어가 `IntegrityError`가 나는데, 168라운드가 세션 삭제 경쟁용으로
      추가해둔 `except IntegrityError: raise _SESSION_NOT_FOUND`가 이걸
      엉뚱하게 "세션 없음"(404)으로 잘못 보고하고, `interview_review_
      service._generate_feedback`은 `ai_feedback`이 nullable이라 아예
      크래시 없이 `NULL`이 조용히 저장되는 데이터 품질 문제였다.

      `app/services/ollama_service.py`의 여섯 곳 모두
      `.get(key) or default` 형태로 바꿔, 값이 없을 때뿐 아니라 명시적
      `null`일 때도 항상 선언된 타입(`str`/`list`)을 반환하도록 했다
      (`chat_stream`의 `chunk.get("message") or {}`도 같은 이유).

      `tests/test_ollama_service.py`에 여섯 메서드 각각에 대해
      `..._is_explicit_null` 테스트를 추가했다 - `chat()`은 `content`가
      null인 경우와 `message` 자체가 null인 경우 둘 다, `chat_stream()`은
      두 청크(`content: null`, `message: null`) 모두에서 아무것도
      yield하지 않는지 확인한다. `git stash`로
      `app/services/ollama_service.py` 수정만 되돌리면 일곱 테스트
      전부 정확히 `AttributeError`로 실패하는 것까지 확인했다.

      전체 502개 테스트 통과, `app/services/ollama_service.py` 100%
      커버리지, `mypy app tests scripts` 클린. 정상 응답(키가 있고
      값이 있는 경우)의 동작은 완전히 그대로라 `docs/
      FRONTEND_INTEGRATION.md` 갱신도, DB 스키마 변경이 없어
      마이그레이션도 필요 없었다.

## 백로그 (151라운드)

- [x] 175. `InterviewPracticeAnswerRequest.answer`/
      `InterviewReviewCreateRequest.content`/
      `InterviewReviewUpdateRequest.content`/`QuizCreateRequest.
      source_text`가 공백-only 값을 그대로 통과시키던 문제 해소 -
      121/122라운드가 "프롬프트로 쓰이는 필드는 대응하는 WS 구현이
      없어 드리프트가 없다"는 이유로 명시적으로 범위 밖에 남겨뒀던
      바로 그 필드들이다. 150라운드까지 이어온 다른 조사 끝에, 아직
      해소되지 않은 채 남아있던 이 항목을 정확히 찾아 마무리했다.

      네 필드 모두 `min_length=1`만 걸려 있어 빈 문자열("")만 막고
      `"   "`(공백만 있는 값)은 그대로 통과시켰다 - `quiz.py`는 한 걸음
      더 미묘한데, `not self.source_text`가 공백 문자열에도 `False`라
      "study_session_id 또는 source_text 중 하나는 필요합니다"
      검증조차 우회했다. 통과하면 AI가 빈 내용으로 질문/피드백/퀴즈를
      생성하고, 그 결과가 되돌릴 방법이 없는(또는 매우 제한적으로만
      되돌릴 수 있는) 형태로 저장된다 - `InterviewPracticeAnswerRequest.
      answer`가 가장 심각한데, `mark_answered_if_pending()`의 단발성
      CAS(`WHERE answer IS NULL`)로 그 턴이 빈 답변인 채 영구히
      소비되고 재제출 엔드포인트가 없다. 나머지 셋은 각각 `update_review`
      (재수정 가능), `PATCH`(재수정 가능, 다만 처음 생성 시점의 값은
      여전히 잘못 남을 수 있음), 퀴즈 삭제 후 재생성(title 외 수정
      불가)으로만 복구 가능하다.

      `app/schemas/interview_practice.py`/`app/schemas/interview_
      review.py`(Create/Update 양쪽)/`app/schemas/quiz.py`에 각각
      `study.py`의 `validate_content_length`(121라운드)와 동일한
      `if not value.strip(): raise ValueError(...)` 패턴을 추가했다.
      `quiz.py`는 기존 검증 순서(`study_session_id`/`source_text` 상호
      배타 확인 → 길이 확인)에 자연스럽게 끼워 넣었다.

      `tests/test_interview_practice.py`/`tests/test_interview_review.py`
      (Create/Update 둘 다)/`tests/test_quiz.py`에 각 필드마다
      `..._rejects_whitespace_only_*` 테스트를 추가했다 - 특히 면접연습
      답변 테스트는 거부된 뒤에도 그 턴이 여전히 미답변 상태로 남아
      나중에 정상적으로 재제출할 수 있는지까지 확인한다. `git stash`로
      스키마 파일 세 개 수정만 되돌리면 네 테스트 모두 정확히 실패(422가
      아니라 실제로 AI 호출까지 진행되어 502/201이 나옴)하는 것까지
      확인했다.

      전체 506개 테스트 통과, `mypy app tests scripts` 클린. 정상
      범위(공백이 아닌) 입력의 동작은 완전히 그대로라 `docs/
      FRONTEND_INTEGRATION.md` 갱신도, DB 스키마 변경이 없어
      마이그레이션도 필요 없었다.

## 백로그 (152라운드)

- [x] 176. `WS_IDLE_TIMEOUT_SECONDS`에 양수 검증 추가 - 159~166/151라운드가
      이어온 "Settings 숫자 필드 검증" 계열이 "완전히 끝남"으로 분류돼
      있었지만, 다시 field-by-field로 훑다가 실제로 빠져 있던 필드
      하나를 발견했다(이 계열이 두 번째로 "끝났다"는 판단이 틀렸던
      사례 - 135/136라운드 때도 같은 일이 있었다).

      학습챗/면접복기 WebSocket 스트리밍 라우트(`routes/study.py`의
      `stream_message`, `routes/interview_review.py`의
      `stream_create_review`)는 매 메시지 대기마다 `asyncio.wait_for(
      websocket.receive_json(), timeout=ws_idle_timeout_seconds)`를
      쓴다. 이 값이 0 이하면 `asyncio.wait_for`가 코루틴이 완료될
      기회조차 주지 않고 즉시 `TimeoutError`를 낸다는 것을 직접
      재현해 확인했다 - 클라이언트가 연결하자마자 메시지를 보내도
      첫 대기에서 곧바로 "idle timeout"으로 연결이 끊겨, 두 스트리밍
      기능 전체가 시작 시점에는 전혀 티가 안 나는 상태로 계속 끊기게
      된다. `MAX_CONCURRENT_WS_CONNECTIONS`(164라운드)와 같은 두
      라우트에 영향을 주지만, 그 검증기 자신의 docstring이 참조하는
      "형제 안전장치"인 이 필드는 정작 검증되지 않은 채 남아있었다.

      `app/core/config.py`에
      `_validate_ws_idle_timeout_seconds_is_positive` field_validator를
      추가했다(`value <= 0`이면 거부, 기존 필드들과 동일한 위치/스타일,
      `max_concurrent_ws_connections` 검증기 바로 앞에 배치).
      `tests/test_config.py`에
      `test_settings_accepts_positive_ws_idle_timeout_seconds`와
      `test_settings_rejects_non_positive_ws_idle_timeout_seconds`
      (0/-1 parametrize)를 추가했다. `git stash`로
      `app/core/config.py` 수정만 되돌리면 두 케이스 모두 정확히
      실패(`ValidationError`가 안 남)하는 것까지 확인했다.

      전체 509개 테스트 통과, 전체 커버리지 99%(`app/core/config.py`
      100% 포함), `mypy app tests scripts` 클린. 정상 범위(양수) 설정의
      동작은 그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      마이그레이션도 필요 없었다.

      (조사 중 `max_interview_questions`/`rag_top_k`/`rag_max_candidate_
      chunks`/`rag_backfill_batch_size`도 함께 재검토했다 - 전부 0
      이하에서 크래시나 전면 장애가 아니라 우아한 성능 저하로 이어져서
      (면접연습이 첫 질문 뒤 바로 끝남, RAG 그라운딩이 빈 배열,
      백필 job이 그날 아무 일도 안 함) 이번 라운드 범위에는 넣지
      않았다.)

## 백로그 (153라운드)

- [x] 177. `/api/v1/chat`(범용 Ollama 프록시)의 `ChatRequest.prompt`가
      공백-only 값을 그대로 통과시키던 문제 해소 - 121/151라운드가 이미
      학습챗/면접연습/면접복기/퀴즈의 프롬프트 필드 전부에 이 검증을
      추가했는데, 정작 가장 단순한(그리고 유일하게 인증 방식도 다른)
      이 프록시 엔드포인트만 빠져 있었다 - 세 라운드 어디에도 `ChatRequest`
      가 언급되지 않아, 의도적 제외가 아니라 단순 누락이었다.

      `docs/FRONTEND_INTEGRATION.md`가 이 엔드포인트를 "4개 실기능과
      무관한 초기 프로토타입용, 신규 프론트 연동에서는 안 씀"으로 이미
      명시하고 있어 다른 세 필드보다 심각도는 낮다 - 아무것도 영구히
      저장되지 않고(단발성 프록시 호출), 응답도 그 자리에서 바로
      돌아간다. 그래도 공백-only `prompt`가 통과하면 의미 없는
      프롬프트로 Ollama 호출만 낭비하게 되는 건 다른 필드들과 동일한
      문제였다.

      `app/schemas/chat.py`의 `validate_prompt_length`에
      `study.py`(121라운드)와 동일한 `if not value.strip(): raise
      ValueError(...)` 검증을 추가했다.

      `tests/test_chat.py`에 `test_chat_rejects_whitespace_only_prompt`를
      추가했다 - 422가 나는지뿐 아니라, `FakeOllamaService.generate()`가
      실제로 한 번도 안 불렸는지(호출 카운터로)까지 확인해 "낭비되는
      호출"이라는 문제 자체가 실제로 막혔는지 검증한다. `git stash`로
      `app/schemas/chat.py` 수정만 되돌리면 이 테스트가 정확히
      실패(200이 나오고 generate()가 호출됨)하는 것까지 확인했다.

      전체 510개 테스트 통과, `app/schemas/chat.py` 100% 커버리지,
      `mypy app tests scripts` 클린. 정상 범위(공백이 아닌) 입력의
      동작은 완전히 그대로라 `docs/FRONTEND_INTEGRATION.md` 갱신도,
      DB 스키마 변경이 없어 마이그레이션도 필요 없었다.

## 백로그 (154라운드)

- [x] 178. `/api/v1/chat`(범용 Ollama 프록시) 라우트를 가리키던 로그
      메시지/주석 세 곳이 실제로 존재하지 않는 `/api/chat`(버전
      프리픽스 누락) 경로를 가리키고 있던 문제 해소 - 153라운드가 다른
      영역들을 전부 훑고도 큰 버그를 못 찾자, 이번 라운드는 "코드
      정확성"이 아니라 "코드가 실제로 하는 일과 주석/로그가 서술하는
      내용이 일치하는가"라는 다른 각도로 조사해 발견했다.

      `git log`로 확인한 결과 이 프록시는 `/api/v1` 버전 프리픽스가
      도입된 최초 커밋부터 계속 `/api/v1/chat`이었는데, 다음 세 곳은
      처음부터(153라운드까지 아무도 못 잡고) `/api/chat`으로 잘못
      쓰여 있었다:
      - `app/main.py`의 `lifespan()` - `API_KEY` 미설정 시 뜨는
        경고 로그(운영자가 실제로 읽는 로그).
      - `app/core/config.py`의 `api_key` 필드 주석.
      - `app/core/config.py`의 `_validate_max_prompt_length_is_positive`
        docstring.

      기능적 영향은 없다(인증 동작, DB 상태, API 응답 어느 것도 바뀌지
      않음) - 순수하게 사람이 읽는 로그/주석이 존재하지 않는 경로를
      가리키던 문서 정확성 문제였다. 세 곳 모두 `/api/v1/chat`으로
      바로잡았다.

      같은 조사 중 `interview_practice_service.py`의
      `_generate_feedback_and_next_question` docstring이 "217번째
      줄 주석 참고"라는 줄 번호로 다른 주석을 가리키고 있었는데,
      `git show`로 추적해보니 이 커밋(150라운드) 당시에도 이미 그
      주석은 217번째 줄이 아니라 259번째 줄에 있었고(애초에 틀린
      참조), 그 뒤 172라운드가 위에 `_generate_first_question`을
      추가하면서 지금은 354번째 줄로 더 밀려나 있었다 - 줄 번호로 된
      참조는 코드가 바뀔 때마다 다시 깨지는 근본적으로 취약한 형태라,
      단순히 숫자를 "354"로 갱신하는 대신 그 주석의 첫 문장("답변을
      먼저 커밋하지 않고...")으로 가리키도록 바꿔 앞으로 코드가
      바뀌어도 안 깨지게 했다. `grep -n "번째 줄"`로 이 파일 전체에
      같은 패턴의 다른 참조가 더 없는지도 확인했다(없음).

      `tests/test_main.py`를 새로 만들어
      `test_startup_warns_with_correct_chat_route_when_api_key_unset`을
      추가했다 - `API_KEY`를 비운 채 `create_app()`을 실행해 lifespan
      시작 시 뜨는 경고 로그를 `caplog`로 잡고(`create_app()`이
      `configure_logging(force=True)`로 root logger 핸들러를 지워버려
      `test_middleware.py`가 이미 쓰던 패턴대로 `create_app()` 이후에
      `"haruhan"` 로거에 핸들러를 다시 붙여야 함), 그 로그가 실제로
      `/api/v1/chat`을 담고 있고 옛 `/api/chat 인증`은 더는 없는지
      확인한다. `git stash`로 `app/main.py` 수정만 되돌리면 이
      테스트가 정확히 실패(옛 문구가 그대로 남아있음)하는 것까지
      확인했다.

      전체 511개 테스트 통과, `app/main.py` 100% 커버리지(신규 파일
      포함 전체 133개 소스 파일), `mypy app tests scripts` 클린. 순수
      로그/주석 문구 수정이라 애플리케이션 동작 변경은 없고,
      `docs/FRONTEND_INTEGRATION.md`는 이미 올바른 경로를 쓰고 있어
      갱신이 필요 없었다. DB 스키마 변경도 없어 마이그레이션도
      필요 없었다.

## 백로그 (155라운드)

- [x] 179. `app/repositories/quiz_repository.py`의
      `get_for_user_locked()` docstring이 "54번 라운드에서 이미 마주친
      것과 같은 성격의 한계"라며 존재하지 않는 선례를 인용하던 문제
      해소 - 154라운드가 시도한 "코드 주석이 실제 사실과 일치하는가"
      감사를 이어가되, 이번엔 경로/줄번호가 아니라 코드 곳곳에 흩어진
      "N번 라운드" 인용 표현을 검증했다.

      이 코드베이스는 "N번 라운드"라는 표현을 두 가지 다른 뜻으로
      섞어 써왔다는 걸 이번에 처음 명시적으로 확인했다 - 대부분은
      로드맵의 백로그 **항목 번호**(`- [x] N.`)를 가리키고(예:
      `interview_practice_service.py`의 "8번 라운드"는 실제로는
      8번째 라운드가 아니라 **항목 8번**을 가리키며, 그 항목의 내용은
      정확히 일치한다), 소수만 실제 **라운드 헤더 번호**(`## 백로그
      (N라운드)`)를 가리킨다(예: `interview_review_repository.py`의
      "143라운드"는 항목 143번이 아니라 라운드 헤더 143이 만든
      항목 167번을 가리키며, 그 내용이 정확히 일치한다). `config.py`의
      네 인용("100번"/"159"/"160"×2/"139")도 이 두 관례 중 하나로는
      전부 실제 내용과 정확히 일치함을 하나하나 확인했다 - 겉보기엔
      혼란스러워도(항목 번호 vs 라운드 헤더 번호가 섞여 있음), 실제로
      "틀린" 인용은 아니었다.

      반면 `quiz_repository.py`의 "54번 라운드"는 **어느 쪽 관례로
      읽어도** 맞지 않았다 - 항목 54번은 접근 로그의 인증 스킴 분기
      테스트 추가(동시성과 무관), 라운드 헤더 54는 (같은 항목 54번을
      만든 라운드라 동일) 역시 무관했다. `git show`로 이 메서드가
      도입된 커밋을 직접 추적해보니(항목 92, "퀴즈 답안 제출의 중복
      방지 로직이..."), 이 메서드 자체가 `SELECT ... FOR UPDATE`+
      "SQLite로는 검증 불가" 패턴을 이 코드베이스에 **처음** 도입한
      자리였다 - 즉 인용할 만한 진짜 선례가 애초에 존재하지 않는데
      숫자만 잘못 적혀 있었다(로드맵 자체의 항목 92 텍스트에도 같은
      실수가 이미 있었던 걸 확인 - 코드 주석이 그 실수를 그대로
      물려받은 것). 반대로 이 패턴을 나중에 따라 쓴
      `interview_practice_repository.py`/`interview_review_repository.py`
      의 같은 docstring은 이미 올바르게 "92번"/"92/101번"을 인용하고
      있었다.

      존재하지 않는 선례를 가리키는 대신, 같은 한계를 공유하는 두
      자매 리포지토리를 직접 가리키도록 docstring을 고쳤다(줄 번호나
      라운드 번호처럼 다시 깨질 수 있는 참조 대신 파일명으로 - 154라운드가
      확립한 "미래에도 안 깨지는 참조" 원칙을 그대로 따름).

      전체 511개 테스트 통과(회귀 없음, 리포지토리 파일 docstring만
      수정), `mypy app tests scripts` 클린. 순수 문서 정확성 수정이라
      애플리케이션 동작 변경은 전혀 없다.

      (`config.py`의 네 인용은 조사 후 실제로는 올바르다고 판단해
      손대지 않았다 - 이번 라운드가 확인한 "항목 번호 vs 라운드 헤더
      번호" 혼용 관례 자체를 이 코드베이스 전체에 걸쳐 일관되게
      통일하는 건 훨씬 큰 작업이라 이번 한 라운드 범위를 벗어난다고
      판단했다. 필요하면 향후 라운드에서 별도로 다룰 수 있다.)

## 백로그 (156라운드)

- [x] 180. `tests/test_quiz.py`의
      `test_get_for_user_locked_requests_row_lock_on_postgres` docstring이
      155라운드가 `app/repositories/quiz_repository.py`에서 고친 것과
      정확히 같은 "54번 라운드" 존재하지 않는 선례 인용을 그대로 갖고
      있던 문제 해소 - 155라운드가 "tests/*.py는 이번 감사 범위 밖"
      이라고 명시적으로 남긴 대로, 이번 라운드가 그 범위를 이어받아
      테스트 파일 쪽을 훑었다.

      `git show`로 확인한 결과, 이 테스트와 리포지토리의 docstring은
      `5dbc7a9`(항목 92, 라운드 헤더 68) 커밋에서 함께 도입됐고 그
      순간부터 둘 다 같은 "54번 라운드" 오기를 갖고 있었다 - 155라운드
      커밋(`5450364`)이 리포지토리 파일만 고치고 이 쌍둥이 테스트
      docstring은 그대로 남겨뒀던 것이다. 항목 54(접근 로그 인증
      스킴 테스트)/라운드 헤더 54(→항목 78, 면접연습 답변 제출 CAS)
      어느 쪽으로 읽어도 SQLite FOR UPDATE 한계와는 무관해, 155라운드가
      내린 것과 같은 결론(이 자리 자체가 이 패턴의 최초 도입 지점이라
      인용할 선례가 애초에 없음)이 그대로 적용된다.

      155라운드가 리포지토리 파일에 적용한 것과 똑같은 방식으로
      고쳤다 - 존재하지 않는 라운드 번호 대신, 같은 한계를 공유하는
      두 자매 리포지토리와 그 근거인 `quiz_repository.py`의 docstring
      자체를 가리키도록 바꿨다.

      이 기회에 `tests/` 전체의 "라운드" 인용 약 20여 개를 155라운드와
      같은 방법(항목 번호 해석과 라운드 헤더 해석 둘 다로 대조)으로
      샘플 검증했다 - `test_quiz.py:626`의 "68/106번 라운드"처럼 얼핏
      의심스러워 보였던 것도 직접 로드맵을 추적해보니 라운드 헤더
      해석으로 정확히 맞았다(라운드 헤더 106 = 항목 130, "pydantic
      에러 메시지 truncation 때문에 회귀 테스트가 수정 전 코드에서도
      통과해버렸던" 바로 그 함정 - 이 세션 시작 시점 요약에서 언급된
      "라운드 106의 truncation-defeats-test-meaning" 사례가 정확히
      이것이었음을 확인). 발견된 것은 위 하나뿐이었다.

      전체 511개 테스트 통과(회귀 없음, 테스트 파일 docstring만 수정),
      `mypy app tests scripts` 클린. 순수 문서 정확성 수정이라
      애플리케이션 동작 변경은 전혀 없다.

## 백로그 (157라운드)

- [x] 181. `.env.example`의 `API_KEY` 주석이 존재하지 않는 `/api/chat`
      (버전 프리픽스 누락) 경로를 가리키던 문제 해소 - 154라운드가
      `app/main.py`/`app/core/config.py`에서 고친 것과 정확히 같은
      버그인데, 그 라운드는 애플리케이션 코드만 감사하고 이 템플릿
      파일은 훑지 않아서 놓쳤다.

      `app/api/v1/router.py`(`prefix="/api/v1"`)와
      `app/api/v1/routes/chat.py`(`prefix="/chat"`)를 다시 확인해
      실제 경로가 여전히 `/api/v1/chat`임을 재확인했다. `git log`로
      `.env.example`이 `/api/v1` 프리픽스 도입 이후에도 이 주석만
      갱신되지 않은 채 남아있었던 것도 확인했다. 저장소 전체를
      `/api/chat` 문자열로 다시 훑어, 남은 참조가 이 한 곳뿐임을
      확인했다(나머지는 전부 Ollama 자신의 업스트림 `/api/chat`
      엔드포인트나 ROADMAP.md의 과거 서술로 무관함).

      `.env.example:18`의 주석을 `/api/v1/chat`으로 바로잡았다.

      `tests/test_docker_compose.py`에
      `test_env_example_api_key_comment_references_versioned_chat_route`
      를 추가했다 - `.env.example`에 `/api/v1/chat`은 있고 버전
      프리픽스 없는 `/api/chat`은 없는지 확인한다. `git stash`로
      `.env.example` 수정만 되돌리면 이 테스트가 정확히 실패(옛
      문구가 그대로 남아있음)하는 것까지 확인했다.

      전체 512개 테스트 통과, `mypy app tests scripts` 클린. 순수
      템플릿 파일 주석 수정이라 애플리케이션 동작 변경은 없고, DB
      스키마 변경도 없어 마이그레이션도 필요 없었다.

## 백로그 (158라운드)

- [x] 182. API 응답의 모든 datetime 필드가 타임존 표기 없이(naive) 직렬화되던
      문제 해소 - `docs/FRONTEND_INTEGRATION.md:302-303`은
      `submitted_at`을 `"2026-08-21T12:00:00Z"`처럼 `Z` 접미사가 붙은
      형태로 문서화하고 있었는데, 실제 앱을 직접 띄워 응답을 찍어보니
      (`create_app()` + `FakeOllamaService`로 학습챗/퀴즈/면접연습/
      면접복기 전체 플로우를 수동으로 실행) 모든 타임스탬프가
      `"2026-08-28T04:36:50.771154"`처럼 `Z`도 오프셋도 없이 나가고
      있었다.

      원인: `app/core/clock.py`의 `utcnow_naive()`가 앱 전체에서
      tz 정보 없는 UTC naive datetime만 저장/사용하도록 통일해뒀는데
      (SQLite/Postgres tz-aware 처리 차이 회피 목적), 어떤 스키마에도
      커스텀 직렬화기(`field_serializer`/`json_encoders`)가 없어
      Pydantic 기본 `datetime.isoformat()`이 그대로 쓰이고 있었다 -
      naive 값에는 `Z`도 오프셋도 붙이지 않는다. ECMA-262 Date Time
      String Format 규격상 `new Date("...")`는 타임존 표기가 없는
      문자열을 UTC가 아니라 **브라우저 로컬 시간**으로 해석하므로,
      `docs/FRONTEND_INTEGRATION.md`가 명시적으로 타겟으로 삼는
      한국(KST, UTC+9) 프론트가 자연스럽게 `new Date(response.created_at)`
      를 쓰면 모든 화면의 타임스탬프가 9시간씩 밀려 보이게 된다 -
      단순 문서 오기가 아니라 실제 프론트 연동 정확성 버그다.

      `app/schemas/validators.py`에 `UtcDatetime` 타입(기존
      `NormalizedEmail`/`NonBlankStr`과 같은 `Annotated` + 후처리
      패턴)을 추가했다 - naive datetime엔 `"Z"`를 붙이고, (이 앱에서는
      나오지 않지만 방어적으로) tz-aware 값은 이미 오프셋이 있으므로
      그대로 둔다. `app/schemas/{auth,export,interview_practice,
      interview_review,quiz,study,user}.py`의 응답 전용 `datetime`
      필드 24개(요청 스키마의 필드는 없음 - 이 앱은 datetime을 입력
      으로 받는 필드가 없다) 전부를 이 타입으로 바꿨다. WebSocket
      스트리밍 라우트(`routes/study.py`, `routes/interview_review.py`)
      는 같은 `*Response` 스키마의 `model_dump(mode="json")`을
      재사용하므로 REST/WS 양쪽 다 한 번에 고쳐진다.

      `tests/test_utc_datetime_serialization.py`를 새로 추가했다 -
      (1) `UtcDatetime` 자체에 대한 순수 단위 테스트 2개(naive 값엔
      `Z`가 붙는지, tz-aware 값엔 중복으로 붙지 않는지), (2) 실제
      FastAPI 엔드포인트(`POST /study/sessions`, `GET /auth/sessions`)
      를 호출해 응답 JSON의 타임스탬프가 실제로 `Z`로 끝나는지 확인
      하는 통합 테스트 2개. `git stash`로 스키마 8개 파일 수정을
      되돌리면 이 테스트 파일이 `ImportError`로 아예 수집 자체가
      안 되는 것까지 확인했다(고치기 전엔 `UtcDatetime`이 존재하지
      않았으므로).

      `docs/FRONTEND_INTEGRATION.md`도 함께 정리했다 - `exported_at`
      예시(`"2026-01-01T00:00:00"`)에 빠져있던 `Z`를 추가했고,
      2절(공통 에러 규칙)에 "응답의 모든 타임스탬프는 `Z` 접미사가
      붙은 UTC ISO 8601"이라는 문장을 명시적으로 추가해, 앞으로
      이 관례가 다시 애매해지지 않도록 했다.

      전체 516개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`app/schemas/validators.py` 100% 커버리지 포함). DB에
      저장되는 값은 여전히 naive UTC 그대로이고 직렬화 방식만
      바뀐 것이라 마이그레이션은 필요 없었다.

## 백로그 (159라운드)

- [x] 183. 활성 refresh token이 하나도 남지 않아 재로그인 자체가 불가능해진
      게스트 계정이 영구히 정리되지 않고 계속 쌓이던 문제 해소 -
      `app/core/scheduler.py`는 정확히 세 개의 daily cron job만 등록하고
      있었고(`keep_supabase_alive`/`cleanup_expired_refresh_tokens`/
      `run_scheduled_rag_backfill`), 그중 `cleanup_expired_refresh_tokens`
      조차 `refresh_tokens` 테이블 행만 지울 뿐 그 소유자인 `User` row는
      전혀 건드리지 않았다. `app/repositories/user_repository.py`에도
      계정을 찾거나 정리하는 메서드가 `get_by_id`/`get_by_email`/`create`/
      `create_guest`/`delete` 외엔 없었다.

      `docs/FRONTEND_INTEGRATION.md:30`이 이미 명시하듯("localStorage를
      지우거나 다른 브라우저/기기로 접속하면 완전히 새로운 방문자로
      취급되고, 이전 데이터에는 다시 접근할 방법이 없습니다") 게스트는
      email/password가 없는 인증 방식이라, 유일한 재접근 수단인 활성
      refresh token이 전부 만료/폐기되고 나면 그 계정과 거기 딸린
      학습챗/퀴즈/면접연습/면접복기/RAG 색인은 본인을 포함해 아무도
      다시 볼 수 없는 채로 무기한 DB에 남는다 - 게스트가 이 앱의
      권장 온보딩 경로(`FRONTEND_INTEGRATION.md`의 "1-0. ... (추천,
      지금 이거 씀)")라 이 죽은 데이터의 비중이 상당할 수 있다.
      `grep`으로 `docs/ROADMAP.md` 전체에서 "게스트" 언급을 확인해
      RAG 청크 개수 상한(94/104/128/131라운드)처럼 스토리지 증가에
      대한 안전장치는 여럿 있었지만, 이 계정 자체의 정리는 어디에도
      명시적으로 다뤄지거나 범위 밖으로 유보된 적이 없었음을 확인했다.

      `app/repositories/user_repository.py`에 `delete_stale_guests(now)`
      를 추가했다 - `email IS NULL`(게스트)이면서 `revoked_at IS NULL
      AND expires_at > now`인 refresh token이 하나도 없는(상관
      서브쿼리 `NOT EXISTS`) 계정만 골라 `delete(User).where(...)`로
      한 번에 지운다. `delete()`와 마찬가지로 User row만 지우면
      나머지는 DB의 `ON DELETE CASCADE`로 함께 지워진다(기존
      `test_account_deletion_cascade.py`가 이미 검증한 것과 동일한
      경로). 실계정(`email`이 있는)은 비밀번호로 언제든 재로그인
      가능하므로 이 조건에서 처음부터 제외했다. 게스트는
      `AuthService.create_guest_session()`이 `create_guest()` 직후
      같은 트랜잭션에서 항상 refresh token을 발급하고 커밋하므로,
      "토큰이 아직 하나도 없는" 갓 생성된 게스트가 이 조건에 잘못
      걸릴 여지도 없다.

      `app/db/session.py`에 `cleanup_stale_guest_accounts()`를
      `cleanup_expired_refresh_tokens()`와 같은 모양(엔진 미초기화
      시 경고 후 건너뜀, `try/except Exception: logger.exception(...)`)
      으로 추가하고, `app/core/scheduler.py`에 네 번째 daily cron
      job(매일 06:00, `misfire_grace_time=None`)으로 등록했다.

      `tests/test_stale_guest_cleanup.py`를 새로 추가했다 - 활성
      토큰이 없는 게스트는 삭제되는지, 그 계정 소유 학습챗 세션까지
      cascade로 함께 지워지는지, 활성 토큰이 있는 게스트는 그대로
      남는지, 실계정은 refresh token이 전부 만료돼도 절대 건드리지
      않는지 확인하는 4개 테스트. `tests/test_db_session.py`에는
      `cleanup_stale_guest_accounts()`의 엔진 미초기화/로깅/실패
      케이스 3개를 기존 `cleanup_expired_refresh_tokens` 테스트와
      같은 패턴으로 추가했다. `tests/test_scheduler.py`의
      `test_scheduled_jobs_never_skip_due_to_misfire`도 job 개수를
      3→4로 갱신했다. `git stash`로 `app/repositories/user_repository.py`
      /`app/db/session.py`/`app/core/scheduler.py` 세 파일만 되돌리면
      새/갱신된 테스트 8개가 전부 (없는 메서드·job 개수 불일치로)
      정확히 실패하는 것까지 확인한 뒤 복원했다.

      전체 523개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`app/repositories/user_repository.py`/`app/db/session.py`
      100% 커버리지 포함). 스키마 변경이 없어 마이그레이션은 필요
      없었고, 프론트가 관찰하는 API 동작(게스트 데이터는 어차피
      재접근 불가로 문서화돼 있음) 자체는 바뀌지 않아
      `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (160라운드)

- [x] 184. `UserService.update_profile()`/`upgrade_guest()`가 계정이 요청 도중
      지워지면 처리되지 않은 `StaleDataError`(500)로 끝나던 문제 해소 -
      143~171라운드가 집중적으로 고친 `IntegrityError`(자식 테이블
      INSERT가 이미 사라진 `user_id` FK를 참조할 때)와는 다른 종류의
      경쟁이다. 이 두 메서드는 이미 로드해둔 `User` ORM 객체의 속성을
      바꾼 뒤 `commit()`에서 SQLAlchemy가 `UPDATE users SET ... WHERE
      id = :id`를 내게 하는데, `get_current_user`가 인증을 확인한
      시점과 이 `commit()` 사이에 다른 요청의 `delete_account()`가(또는
      159라운드가 막 추가한 `cleanup_stale_guest_accounts` cron job이)
      먼저 그 행을 지워버리면 이 UPDATE가 0행에 매치되고, SQLAlchemy의
      ORM 계층이 기본으로 이를 감지해 `StaleDataError`를 던진다(버전
      컬럼 등 별도 설정 없이도 항상 켜져 있는 동작).

      직접 재현 스크립트로 확인했다: 세션 A에서 게스트를 로드해두고
      세션 B로 같은 계정을 완전히 지운 뒤, 세션 A에서 속성만 바꾸고
      커밋하면 정확히 `sqlalchemy.orm.exc.StaleDataError: UPDATE
      statement on table 'users' expected to update 1 row(s); 0 were
      matched.`가 난다. `grep -rn StaleDataError app/`로 이 예외가
      앱 어디에서도 다뤄지지 않고 있음을 확인했다. 실제로 재현
      가능한 경로: (1) 같은 계정을 두 탭/기기로 열어두고 한쪽에서
      계정 삭제, 다른 쪽에서 거의 동시에 프로필 수정, (2) 게스트가
      `/auth/logout`으로 유일한 refresh token을 폐기한 직후, 아직
      만료 전인 access token으로 `/users/me/upgrade`를 부르는 사이에
      마침 `cleanup_stale_guest_accounts`(매일 06:00) cron이 그 계정을
      정리해버리는 경우.

      `app/services/user_service.py`에 다른 세 서비스(`study_service.py`
      /`interview_practice_service.py`/`interview_review_service.py`,
      146라운드)와 정확히 같은 코드/메시지의 `_ACCOUNT_GONE`
      상수(401, `{"code": "invalid_token", ...}`)를 추가하고,
      `update_profile()`/`upgrade_guest()` 양쪽의 기존 `except
      IntegrityError:` 블록 옆에 `except StaleDataError:` 분기를
      더해 같은 401로 변환하도록 했다 - 재시도해도 `get_current_user`
      가 어차피 이 코드로 401을 낼 상황이라 클라이언트 입장에서
      동일하게 다뤄야 하는 것도 기존 패턴과 같다.

      `tests/test_users.py`에 두 메서드 각각에 대한 회귀 테스트를
      추가했다 - 143라운드 계열이 확립한 "리포지토리 메서드를
      몽키패치해 그 안에서 별도 세션으로 실제 삭제를 수행" 기법을
      그대로 썼다(`get_by_email` 호출 직후 계정을 지우도록). `git
      stash`로 `user_service.py`만 되돌리면 두 테스트 모두 (500으로
      새어나가는 `StaleDataError`를 pytest가 그대로 잡아) 정확히
      실패하는 것까지 확인한 뒤 복원했다.

      전체 525개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`app/services/user_service.py` 100% 커버리지 유지). 스키마
      변경이 없어 마이그레이션은 필요 없었고, 이미 다른 세 서비스가
      같은 코드로 401을 내고 있어 `FRONTEND_INTEGRATION.md`가 이미
      문서화한 계약과 일치하므로 갱신도 필요 없었다.

## 백로그 (161라운드)

- [x] 185. 학습챗/퀴즈/면접연습 이름변경(rename) 세 엔드포인트가 그 리소스
      자체가 요청 도중 지워지면 처리되지 않은 `StaleDataError`(500)로
      끝나던 문제 해소 - 184라운드가 고친 "계정 자체가 지워지는" 경쟁과는
      다른 종류다. `StudyService.rename_session()`/`QuizService.
      rename_quiz()`/`InterviewPracticeService.rename_session()` 셋 다
      `get_for_user()`(잠금 없는 조회)로 리소스를 읽은 뒤
      `update_title()`/`update_topic()`으로 속성만 바꾸는 구조인데
      (`submit_answer`/`complete_session`/`update_review`가 쓰는
      `get_for_user_locked()`와 다름), 이 조회와 그 UPDATE 사이에 다른
      요청이 `DELETE /study/sessions/{id}`(또는 퀴즈/면접연습 버전)로
      같은 리소스를 지워버리면 UPDATE가 0행에 매치돼 `StaleDataError`가
      난다 - 계정은 멀쩡한 채 이 리소스 하나만 지워지는 경우라 184라운드의
      수정이 커버하지 못한다.

      직접 재현 스크립트로 확인했다: 세션 A에서 학습챗 세션을 읽어두고
      세션 B로 같은 세션을 완전히 지운 뒤, 세션 A에서
      `StudySessionRepository.update_title()`을 부르면 정확히
      `StaleDataError: UPDATE statement on table 'study_sessions'
      expected to update 1 row(s); 0 were matched.`가 난다는 것도
      확인했다 - 예외가 실제로 나는 지점은 나중의 `session.commit()`이
      아니라 `update_title()`/`update_topic()` 내부의 `flush()` 호출
      이라, 그 호출까지 함께 `try` 블록으로 감싸야 한다는 걸 이 재현으로
      알아냈다. `grep -rn StaleDataError app/`로 `user_service.py`
      외엔 아무 데도 이 예외가 다뤄지지 않고 있음을 재확인했다.

      세 서비스 파일 모두 `update_title()`/`update_topic()` 호출과
      `commit()`을 `try: ... except StaleDataError:` 블록으로 감싸,
      이미 있는 "리소스 없음" 404(`_SESSION_NOT_FOUND`/`_QUIZ_NOT_FOUND`
      /`_NOT_FOUND`)로 변환하도록 고쳤다 - 계정이 아니라 리소스가
      사라진 경우라 184라운드의 401(`_ACCOUNT_GONE`)이 아니라, 존재하지
      않는 리소스를 상대로 한 다른 요청과 같은 404가 맞다.

      `tests/test_study.py`/`tests/test_quiz.py`/
      `tests/test_interview_practice.py`에 각각 회귀 테스트를 추가했다 -
      143라운드 계열이 확립한 "리포지토리 메서드를 몽키패치해 그 안에서
      별도 세션으로 실제 삭제를 수행" 기법을 그대로 썼다(`update_title`/
      `update_topic` 호출 직전에 리소스를 지우도록). `git stash`로 세
      서비스 파일만 되돌리면 세 테스트 모두 (500으로 새어나가는
      `StaleDataError`를 pytest가 그대로 잡아) 정확히 실패하는 것까지
      확인한 뒤 복원했다.

      전체 528개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(세 서비스 파일 전부 100% 커버리지 유지). 스키마 변경이 없어
      마이그레이션은 필요 없었고, 이미 존재하는 404 응답과 코드/의미가
      동일해 `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (162라운드)

- [x] 186. `AuthService.revoke_session()`이 대상 refresh token이 요청 도중
      지워지면 처리되지 않은 `StaleDataError`(500)로 끝나던 문제 해소 -
      184/185라운드가 각각 `users` 테이블 UPDATE(계정 자체 수정)와
      학습챗/퀴즈/면접연습 세 리소스 테이블 UPDATE(이름변경)에서 고친
      것과 같은 종류의 경쟁을 `refresh_tokens` 테이블에서도 겪고 있었다.
      `revoke_session()`은 `get_active_by_id_for_user()`(잠금 없는
      조회)로 세션을 읽은 뒤 `RefreshTokenRepository.revoke()`(`token.
      revoked_at = ...` + `flush()`, 개별 ORM UPDATE)로 폐기하는 구조라,
      그 조회와 UPDATE 사이에 다른 요청이 `DELETE /users/me`로 이 계정을
      지우면(FK가 `ON DELETE CASCADE`라 `refresh_tokens` 행도 함께
      사라짐) UPDATE가 0행에 매치돼 `StaleDataError`가 난다.
      `grep -rn StaleDataError app/services/auth_service.py`로 이
      파일이 184/185라운드 어느 쪽에도 포함되지 않아 이 예외가 전혀
      다뤄지지 않고 있었음을 확인했다.

      직접 재현 스크립트로 확인했다: 세션 A에서 활성 refresh token을
      만들어두고 세션 B로 그 소유 계정을 완전히 지운 뒤, 세션 A에서
      `RefreshTokenRepository.revoke()`를 부르면 정확히 `StaleDataError:
      UPDATE statement on table 'refresh_tokens' expected to update
      1 row(s); 0 were matched.`가 난다는 것도 확인했다. `revoke_all_
      sessions()`(전체 로그아웃)는 `WHERE user_id = :id`를 건 Core
      벌크 UPDATE라 이 문제와 무관함도 코드로 확인했다(개별 ORM
      UPDATE만 "기대한 행 수"를 검사해 이 예외를 던진다).

      `app/services/auth_service.py`의 `revoke_session()`에서
      `revoke()`+`commit()` 호출을 `try: ... except StaleDataError:`
      블록으로 감싸, 이미 있는 `_SESSION_NOT_FOUND`(404)로 변환하도록
      고쳤다 - 계정이 아니라 이 refresh token(세션) 자체가 사라진
      경우라, 존재하지 않는 session_id를 상대로 한 다른 요청과 같은
      404가 185라운드와 같은 이유로 맞다.

      `tests/test_auth.py`에 143라운드 계열이 확립한 "리포지토리
      메서드를 몽키패치해 그 안에서 별도 세션으로 실제 삭제를 수행"
      기법(이 파일의 `test_refresh_returns_401_when_account_deleted_
      before_user_lookup` 등과 같은 패턴)으로 회귀 테스트를 추가했다.
      `git stash`로 `auth_service.py`만 되돌리면 이 테스트가 (500으로
      새어나가는 `StaleDataError`를 pytest가 그대로 잡아) 정확히
      실패하는 것까지 확인한 뒤 복원했다.

      전체 529개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`auth_service.py` 100% 커버리지 유지). 스키마 변경이 없어
      마이그레이션은 필요 없었고, 이미 존재하는 404 응답과 코드/의미가
      동일해 `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다. 이로써
      184/185/186라운드가 `StaleDataError`가 날 수 있는 모든 unlocked
      UPDATE 경로(계정 자체, 학습챗/퀴즈/면접연습 리소스, refresh
      token)를 전부 커버했다 - `*_locked()`를 쓰는 메서드들은 92~103
      라운드의 잠금으로 이미 안전하다.

## 백로그 (163라운드)

- [x] 187. 121/146/151/153/175라운드가 추가한 "공백-only 입력 거부" 검증이
      보이지 않는 유니코드 문자로 우회 가능했던 문제 해소 - 이 검증들은
      전부 `not value.strip()` 패턴을 쓰는데, `str.strip()`은
      `str.isspace()`가 True인 공백류 문자만 제거하고, zero-width
      space(U+200B)/ZWNJ(U+200C)/ZWJ(U+200D)/word joiner(U+2060)/
      BOM(U+FEFF)처럼 화면엔 아무것도 안 보이지만 공백이 아닌 유니코드
      Cf("서식") 카테고리 문자는 그대로 남긴다 - `'​'.isspace()`가
      `False`이고 `'​'.strip()`이 `'​'`(제거 안 됨) 그대로임을
      직접 확인했다. 그 결과 이런 문자로만 이루어진 문자열은
      `not value.strip()`가 `False`(="비어있지 않음")로 나와, 화면엔
      완전히 빈 것처럼 보이는 값이 검증을 통과해버린다.

      실제 앱을 띄워 재현했다: `POST /study/sessions/{id}/messages`에
      `{"content": "​​"}`을 보내면 `200`으로 저장되고 실제
      Ollama `chat()` 호출까지 발생했다(이 검증이 121라운드에 막으려던
      바로 그 낭비). `POST /interview/practice-sessions/{id}/answers`도
      같은 값을 스키마 검증 통과시켰다. 영향받는 지점은
      `app/schemas/validators.py`(`NonBlankStr`가 거치는 `_reject_blank`
      - 학습챗/퀴즈/면접연습/면접복기의 제목·주제·회사명·직무명 라벨
      필드 전부가 이걸 공유), `app/schemas/study.py`(메시지 content),
      `app/schemas/chat.py`(prompt), `app/schemas/quiz.py`(source_text),
      `app/schemas/interview_practice.py`(answer),
      `app/schemas/interview_review.py`(생성/수정 content 둘 다) 총
      7곳 - 전부 같은 결함을 공유하는 하나의 근본 원인이다. WS 스트리밍
      경로(`routes/study.py`의 `stream_message`)도 Pydantic을 거치지
      않는 자체 검증(`not content.strip()`)이라 같은 문제가 있어 함께
      고쳤다(면접복기 WS는 `InterviewReviewCreateRequest.model_validate()`
      를 그대로 쓰므로 스키마 수정만으로 자동으로 커버됨).

      `app/schemas/validators.py`에 `is_blank(value)` 헬퍼를 추가했다 -
      문자열의 모든 문자가 공백류(`isspace()`)이거나 유니코드 Cf
      카테고리인지 확인한다(`unicodedata.category(ch) == "Cf"`). 위
      7곳의 `not value.strip()`/`not self.source_text.strip()`을 전부
      이 헬퍼 호출로 바꿨다. `app/services/quiz_service.py:101`(학습
      세션에 메시지가 있는지 확인 - "role: " 접두사가 항상 붙어 순수
      비가시 문자만으로는 절대 도달 못 하는 분기라 무관)과
      `app/services/rag_service.py:62`(색인을 건너뛸지 결정하는 내부
      최적화 가드, 사용자에게 보이는 거부 응답이 아니고 스키마 검증을
      통과한 값만 들어옴)는 검토 후 이 벡터와 무관하다고 판단해 손대지
      않았다.

      `tests/test_schemas_validators.py`에 `is_blank()` 자체에 대한
      단위 테스트(대표적인 Cf 문자 5종 + 여러 개 조합이 blank로 판정,
      보이는 문자와 섞이면 blank 아님)와, 기존
      `test_whitespace_only_label_field_is_rejected`와 같은
      파라미터 목록을 재사용한 "비가시 문자 라벨 필드 거부" 테스트를
      추가했다. `tests/test_study.py`(REST+WS 둘 다)/
      `tests/test_chat.py`(Ollama 미호출까지 확인)/`tests/test_quiz.py`
      /`tests/test_interview_practice.py`/`tests/test_interview_review.py`
      (생성+수정 둘 다)에도 각 필드의 기존 "공백-only 거부" 테스트
      바로 옆에 짝을 이루는 비가시 문자 버전을 추가했다 - 총 7개 파일에
      걸쳐 다수의 회귀 테스트. `git stash`로 스키마/라우트 파일들만
      되돌리면 이 새 테스트들이 전부 (기대한 422 대신 200/201을 받아)
      정확히 실패하는 것까지 확인한 뒤 복원했다.

      전체 549개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`app/schemas/validators.py` 100% 커버리지 포함). 순수
      검증 로직 수정이라 DB 스키마 변경이 없어 마이그레이션은 필요
      없었고, 거부 대상이 넓어졌을 뿐 정상 입력의 동작은 그대로라
      `FRONTEND_INTEGRATION.md` 갱신도 필요 없었다.

## 백로그 (164라운드)

- [x] 188. 면접복기 `interview_date`의 "미래 날짜 거부" 검증이 서버의 UTC
      달력일만 기준으로 비교해, UTC보다 앞선 시간대(KST 등) 사용자의
      정당한 "오늘" 날짜를 미래로 오판해 거부하던 문제 해소 -
      `app/schemas/interview_review.py`의
      `_validate_interview_date_not_in_future()`(110라운드/항목 134가
      도입)는 `utcnow_naive().date()`(서버 UTC 기준 오늘)와 비교하는데,
      `interview_date`는 tz 정보 없는 순수 날짜라 사용자의 로컬 달력
      날짜를 뜻한다. 이 앱은 한국어 UI로 KST(UTC+9)를 주 대상으로 하는데
      (182라운드가 `UtcDatetime` 도입 근거로도 확인한 사실), UTC 자정
      전(KST로는 이미 다음날 오전, 하루 24시간 중 9시간에 해당하는 구간)
      KST 사용자가 자신의 "오늘" 날짜를 보내면, 서버 UTC 기준으로는
      아직 "내일"이라 미래 날짜로 오판해 거부해버린다.

      `utcnow_naive`를 실제 UTC 20:00으로 몽키패치해 KST "오늘"(=UTC
      기준 "내일") 날짜를 보내면 정확히 거부됨을 직접 재현해 확인했다.
      이 검증의 기존 회귀 테스트(`test_create/update_review_accepts_
      todays_interview_date`)는 프로덕션 코드와 똑같이 `utcnow_naive()`
      로 "오늘"을 계산해 이 시간대 어긋남 자체를 볼 수 없는 구조라
      (자기 자신과만 비교), 이 버그가 지금까지 안 걸린 이유였다.

      `_validate_interview_date_not_in_future()`의 비교 기준을
      `today`에서 `today + timedelta(days=1)`로 바꿔, UTC보다 앞선
      시간대와의 어긋남을 흡수하는 하루의 여유를 뒀다 - "정확한 하한이
      아니라 넉넉한 안전장치"라는, 이 코드베이스의 다른 소프트 상한들과
      같은 원칙이다. `interview_date`를 쓰는 유일한 두 필드
      (`InterviewReviewCreateRequest`/`UpdateRequest`)가 이 헬퍼 하나를
      공유해 자동으로 함께 고쳐진다. `grep ": date\\b" app/schemas/*.py`
      로 `interview_date`가 스키마 계층에서 유일한 순수 `date`(datetime
      아님) 사용자 입력 필드임을 확인해, 이 패턴이 다른 곳에 더 없음을
      확인했다.

      `tests/test_interview_review.py`의 기존 "미래 날짜 거부"
      테스트 2개(생성/수정)를 "내일"이 아니라 "2일 뒤"로 갱신했다
      (새 하루 여유 안에 들어와 더는 거부 케이스가 아니게 됐으므로).
      "UTC 기준 내일 = KST 사용자의 오늘" 날짜가 생성/수정 둘 다 정상
      허용되는지 확인하는 회귀 테스트 2개를 새로 추가했다. `git stash`로
      스키마 파일만 되돌리면 이 새 테스트 2개가 정확히 (기대한 200/201
      대신 422를 받아) 실패하는 것까지 확인한 뒤 복원했다.

      `docs/FRONTEND_INTEGRATION.md`의 면접복기 절에 이 하루 여유를
      한 줄로 명시했다 - 사용자가 관찰 가능한 검증 경계 변경이라
      110라운드/항목 134가 세운 문서화 관례를 따랐다.

      전체 551개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린. 스키마 필드 자체는 그대로고 검증 로직만 바뀐 것이라
      DB 스키마 변경/마이그레이션은 필요 없었다.

## 백로그 (165라운드)

- [x] 189. `QuizService.create_quiz()`가 직접 붙여넣은 소스로 퀴즈를 만들 때
      (`study_session_id`를 지정하지 않은 경우) AI 생성 도중 계정이
      지워지면, "Study session not found"(404)라는 엉뚱한 오답을 내던
      문제 해소 - 143~147라운드가 다른 서비스들에 적용한 "계정 삭제
      경쟁"(check-then-act 중 참조 대상이 지워지면 나중 INSERT가
      IntegrityError로 실패) 계열인데, 147라운드의 전수 재점검이 정확히
      이 메서드만 놓쳤다. 147라운드 자체의 기록(`## 백로그 (147라운드)`)
      을 다시 읽어보면 `quiz_service.submit_answers`는 점검해 안전하다고
      확인했지만 `create_quiz()`는 언급조차 되지 않아, "소진됐다"는
      선언이 이 메서드까지는 실제로 검증한 게 아니었음을 확인했다.

      `create_quiz()`는 `study_session_id`가 있을 때만 그 부모 학습
      세션(`source_study_session_id`, `ondelete="SET NULL"`)이 AI 호출
      도중 지워지는 경우를 다루도록 만들어졌는데(그때도 IntegrityError는
      나는데, 이유는 "삭제 자체가 CASCADE라서"가 아니라 "INSERT 시점에
      이미 사라진 부모를 참조하려 해서"), `study_session_id`가 없는(직접
      붙여넣기) 경로는 이 INSERT가 참조하는 FK가 `user_id`
      (`nullable=False`, `ondelete=CASCADE`) 하나뿐이라 IntegrityError의
      원인이 "계정 자체가 지워졌다"일 수밖에 없다. 그런데도 기존 코드는
      두 경로를 구분하지 않고 전부 "Study session not found"로 답해,
      요청에 `study_session_id`를 넣은 적도 없는 사용자에게 있지도 않은
      세션 얘기를 하는 오답을 내고 있었다.

      직접 재현 스크립트로 확인했다: `study_session_id=None`으로 퀴즈
      생성을 시작하고, 가짜 Ollama가 응답을 반환하기 "직전" 별도
      세션에서 계정을 완전히 지우면 `create_quiz()`가 정확히
      `404 Study session not found`를 반환한다는 것도 확인했다(고치기
      전 상태로).

      `app/services/quiz_service.py`에 다른 세 서비스와 같은
      `_ACCOUNT_GONE`(401, `{"code": "invalid_token", ...}`) 상수를
      추가하고, `except IntegrityError:` 분기를
      `study_session_id is None`이면 `_ACCOUNT_GONE`, 아니면(=요청에
      명시된 학습 세션이 있었던 경우) 기존처럼 `_SESSION_NOT_FOUND`로
      나누도록 고쳤다 - 후자는 계정이 아니라 그 세션만 지워졌을 가능성도
      있어, "그 리소스는 더는 없다"는 404가 여전히 정확하고 실행 가능한
      답이기 때문에 그대로 뒀다.

      `tests/test_quiz_session_deleted_race.py`에 기존 "학습 세션 삭제"
      테스트와 짝을 이루는 "계정 삭제"(직접 붙여넣기 경로) 테스트를
      추가했다 - 같은 "가짜 Ollama가 응답 직전에 별도 세션에서 실제로
      지운다" 기법을 그대로 썼다. `git stash`로 `quiz_service.py`만
      되돌리면 이 새 테스트가 정확히 (404를 받아 기대한 401과 다름)
      실패하는 것까지 확인한 뒤 복원했다.

      전체 552개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`quiz_service.py` 100% 커버리지 유지). 스키마 변경이 없어
      마이그레이션은 필요 없었고, 다른 세 서비스가 이미 같은 코드로
      401을 내고 있어 `FRONTEND_INTEGRATION.md`가 이미 문서화한 계약과
      일치하므로 갱신도 필요 없었다.

## 백로그 (166라운드)

- [x] 190. `/health/ready`(오케스트레이터/로드밸런서용 readiness probe)가
      DB/Redis/Ollama 각각을 확인할 때 자체 타임아웃이 전혀 없어, 상대가
      완전히 죽은 게 아니라 응답만 느려지는 상황에서는 확인 하나가 최대
      60초까지 걸릴 수 있던 문제 해소 - `check_db_health()`(연결 새로
      맺을 때 asyncpg 기본 연결 타임아웃 60초)/`check_redis_health()`
      (redis-py `socket_timeout`/`socket_connect_timeout` 기본값 5초)/
      `check_ollama_health()`(`OllamaService` 기본 60초)가 전부 그
      클라이언트 라이브러리 자신의 기본 타임아웃을 그대로 물려받고
      있었다. readiness probe는 원래 몇 초 안에 빠르게 답해야 트래픽
      라우팅 판단에 의미가 있는데, 세 확인이 `_readiness_cache_lock`
      아래 순차로 실행돼(`app/api/v1/routes/health.py`) 셋 중 하나만
      느려져도 그 시간 동안 캐시가 비어있는 다른 모든 폴러까지 함께
      멈춰 기다리게 된다.

      실제 소켓을 열고 응답만 안 주는 블랙홀 서버로 `check_ollama_health`
      를 직접 재현해, 타임아웃 없이는 확인 하나가 정확히 그 대기 시간만큼
      (1초/2.5초 등) 걸린다는 것을 확인했다. 91라운드가 이미 "헬스체크가
      이벤트 루프를 막는가"를 검토해 기각한 적이 있지만, 그건 "블로킹
      I/O인가"라는 질문이었고 이번 건은 "이 타임아웃이 probe에 적합한
      길이인가"라는 다른 질문이다 - 149라운드는 캐싱/락으로 호출 *빈도*를
      줄였을 뿐 호출 *소요 시간* 자체는 다루지 않았다.

      `app/core/config.py`에 `health_check_timeout_seconds: float = 3.0`
      을 다른 숫자 설정들과 같은 `field_validator`(0 이하 거부) 패턴으로
      추가했다 - `rate_limit.py`의 `REDIS_SOCKET_TIMEOUT_SECONDS`(1초,
      147라운드)와 같은 "정상 왕복 시간보다 훨씬 넉넉하지만 무한정은
      아닌" 상한 철학이다. `app/core/health.py`의 `check_redis_health`/
      `check_ollama_health`와 `app/db/session.py`의 `check_db_health`
      모두 이 값을 인자로 받아 `asyncio.wait_for(..., timeout=...)`로
      감쌌다(Redis는 라이브러리 내부 소켓 타임아웃에만 기대지 않도록
      `socket_timeout`/`socket_connect_timeout` 전달과 `wait_for`를
      둘 다 적용). `app/api/v1/routes/health.py`의 `_get_or_check_readiness`
      가 이 값을 세 함수에 전달하도록 고쳤다.

      `tests/test_core_health.py`(Redis/Ollama가 "응답은 하지만 느린"
      경우 짧은 타임아웃 안에 실패 판정되는지, `socket_timeout`이 실제로
      전달되는지), `tests/test_db_session.py`(DB 쿼리가 느린 경우도
      동일), `tests/test_config.py`(새 설정의 양수 검증)에 회귀 테스트를
      추가하고, `tests/test_health.py`의 기존 가짜 `check_db_health`/
      `check_redis_health` 더블들이 새 `timeout_seconds` 인자를 받도록
      갱신했다. `.env.example`/`docker-compose.yml`에도
      `HEALTH_CHECK_TIMEOUT_SECONDS`를 추가해 113/120라운드가 세운
      "모든 Settings 필드는 컨테이너까지 전달돼야 한다" 관례를
      `test_docker_compose.py`의 전수 확인 테스트로 계속 만족시켰다.
      `git stash`로 스키마/헬스체크 파일들만 되돌리면 새/갱신된 테스트
      19개가 전부 (없는 인자·타임아웃 미적용으로) 정확히 실패하는 것까지
      확인한 뒤 복원했다.

      전체 559개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`app/core/health.py`/`app/db/session.py`/
      `app/api/v1/routes/health.py`/`app/core/config.py` 전부 100%
      커버리지 유지). DB 스키마 변경이 없어 마이그레이션은 필요 없었다.

## 백로그 (167라운드)

- [x] 191. `/health/ready`의 DB/Redis/Ollama 세 확인이 순서대로(직렬로)
      실행돼, 각 확인이 166라운드가 건 `health_check_timeout_seconds`
      안에 끝나더라도 셋이 동시에 느려지는 실제 장애 상황에서는 전체
      응답 시간이 그 합(최대 3배, 기본값 기준 최대 9초)까지 늘어나던
      문제 해소 - 166라운드 자신의 커밋 메시지(`docs/ROADMAP.md`)가
      "세 확인이 `_readiness_cache_lock` 아래 순차로 실행돼... 다른
      모든 폴러까지 함께 멈춰 기다리게 된다"는 사실 자체는 이미 정확히
      언급했지만, 그 라운드가 고친 건 확인 "개별" 소요 시간의 상한일
      뿐 "합산" 소요 시간은 다루지 않아 목표("readiness probe는 몇 초
      안에 빠르게 답해야 트래픽 라우팅 판단에 의미가 있다")를 절반만
      달성한 상태였다. readiness probe는 여러 의존성이 한꺼번에
      느려지는 진짜 장애 상황에서 오히려 가장 빠르게 답해야 의미가
      있는데, 오케스트레이터 자신의 probe 타임아웃(대개 이 앱의 상한
      보다 짧게 잡힘)이 앱이 판단을 끝내기도 전에 먼저 끊어버려 부정확한
      "unready" 판정으로 이어질 수 있었다.

      `app/api/v1/routes/health.py`의 `_get_or_check_readiness()`가
      실제로 `db_ok = await check_db_health(...)` →
      `redis_ok = await check_redis_health(...)` →
      `ollama_ok = await check_ollama_health(...)`를 순서대로 부르고
      있음을 코드로 확인했고, 3개 모두 1초 지연으로 흉내낸(각각
      `asyncio.wait_for(timeout=1.0)`로 개별 제한을 걸어둔 채) 직접
      재현 스크립트로 순차 실행 시 약 3.0초, `asyncio.gather`로 동시
      실행 시 약 1.0초가 걸린다는 것도 확인했다.

      `settings.redis_url`이 없으면 Redis 확인 자체를 건너뛰고
      `"not_configured"`를 매기는 기존 분기를 `_check_redis_status()`
      헬퍼로 그대로 옮기고, `check_db_health`/`_check_redis_status`/
      `check_ollama_health` 세 코루틴을 `asyncio.gather`로 동시에
      실행하도록 고쳤다 - 전체 대기 시간이 이제 가장 느린 확인
      하나(≈`health_check_timeout_seconds`)에 가깝게 끝난다.

      `tests/test_health.py`에
      `test_get_or_check_readiness_runs_db_redis_ollama_checks_concurrently`
      를 추가했다 - DB/Redis/Ollama 세 확인을 전부 0.2초 지연으로
      흉내내고, 전체 응답 시간이 순차 실행이라면 나올 최소 0.6초보다
      한참 짧은지 확인한다. `git stash`로 `health.py`만 되돌리면 이
      테스트가 실제로 약 0.6초(정확히 세 지연의 합)가 걸려 정확히
      실패하는 것까지 확인한 뒤 복원했다.

      전체 560개 테스트 통과(회귀 없음), `mypy app tests scripts`
      클린(`app/api/v1/routes/health.py` 100% 커버리지 유지). 응답
      바디/상태 코드 계약은 그대로고 내부 실행 순서만 바뀐 것이라
      DB 스키마 변경/마이그레이션도, `FRONTEND_INTEGRATION.md` 갱신도
      필요 없었다.

