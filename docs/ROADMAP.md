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
- [ ] 14. 구조화된 액세스 로그 미들웨어 — 지금은 처리되지 않은 예외만
      로깅됨. 정상 요청도 method/path/status/처리시간/user_id(있으면)를
      구조화된 형태로 로깅.
- [ ] 15. RAG 백필 스크립트 스케줄러 자동화 — `scripts/backfill_knowledge_chunks.py`가
      지금은 수동 실행 스크립트로만 존재. 색인 실패했던 항목을 주기적으로
      재시도하는 용도로 스케줄러 job화 (매번 전체를 다시 긁는 게 아니라,
      아직 색인 안 된 것만 대상으로 하는 방식 고민할 것).
- [ ] 16. 데이터 export(JSON) — 사용자가 자기 학습챗/퀴즈/면접 기록을
      JSON으로 내보낼 수 있는 엔드포인트. PDF는 이번 라운드 범위 밖(별도
      라이브러리 의존성 검토 필요) - JSON만.
- [ ] 17. Prometheus 메트릭 + Grafana — FastAPI에 `/metrics` 엔드포인트를
      노출(요청 수/지연시간/상태코드 등 기본 메트릭 + 가능하면 회원가입/게스트
      전환/퀴즈 생성 같은 비즈니스 카운터 몇 개). docker-compose에 prometheus,
      grafana 서비스 추가하고 prometheus가 haruhan-backend의 /metrics를
      스크레이프하도록 설정. Grafana는 Prometheus 데이터소스만 미리
      프로비저닝해두고, 대시보드 패널 구성까지는 이번 범위 밖(사람이 나중에
      직접 만듦) - 데이터소스 연결까지만 자동화.
