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
