# 프론트엔드 연동 가이드

haruhan-backend API와 프론트엔드를 연동하기 위한 참고 문서입니다. 지금 프론트에는 로그인이 전혀 구현되어 있지 않은 상태를 기준으로, 처음부터 끝까지 필요한 것만 정리했습니다.

## 0. 준비 사항

- **Base URL**: `https://<DOMAIN>` (Caddy 리버스 프록시 적용 후. HTTPS 없이 IP로 직접 호출하면 브라우저가 Mixed Content로 막습니다)
- **CORS**: 백엔드의 `CORS_ORIGINS` 환경변수에 프론트 origin(예: `https://mindulmenduls-projects.vercel.app`)이 정확히 등록되어 있어야 브라우저에서 호출이 가능합니다. 쿠키를 쓰지 않으므로 fetch에 `credentials: 'include'`는 필요 없습니다.
- 모든 요청/응답은 JSON (`Content-Type: application/json`)이고, 모든 API 경로는 `/api/v1` 프리픽스가 붙습니다.

## 1. 인증 흐름

이 API는 쿠키가 아니라 **Bearer 토큰** 방식입니다. 발급받은 `access_token`을 매 요청의 `Authorization` 헤더에 실어야 합니다.

### 1-0. 로그인 폼 없이 쓰기 — 게스트 토큰 (추천, 지금 이거 씀)

**지금 프론트는 로그인 UI를 만들 계획이 없지만, 방문자별로 데이터는 분리되어야 합니다.** 이럴 때 쓰라고 만든 엔드포인트입니다.

```
POST /api/v1/auth/guest        (바디 없음)
```
→ `201`, 응답은 로그인과 완전히 같은 모양:
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

사용 방법: **앱이 처음 켜질 때, `localStorage`에 저장된 토큰이 없으면 이 API를 한 번 호출**해서 받은 토큰을 저장해두면 끝입니다. 회원가입/로그인 화면 자체가 필요 없습니다. 이후로는 1-3, 1-4에 나온 대로 `Authorization` 헤더 붙이고, 401 나면 refresh하면 됩니다.

**주의할 점 (중요)**:
- 게스트 계정은 email/password가 없습니다. `localStorage`를 지우거나 다른 브라우저/기기로 접속하면 **완전히 새로운 방문자로 취급되고, 이전 데이터에는 다시 접근할 방법이 없습니다** (이메일 같은 복구 수단이 없음).
- 그러니 프론트에서 게스트 토큰을 받으면 `localStorage`에서 절대 지우면 안 되고(로그아웃 버튼이 없다면 더더욱), 앱 재실행 시 기존 토큰이 있으면 `/auth/guest`를 다시 호출하지 말고 그 토큰을 그대로 재사용해야 합니다.
- 나중에 진짜 회원가입/로그인 UI를 붙이더라도, 기존 게스트 계정의 데이터를 이메일 계정으로 옮기는 기능은 아직 없습니다 (필요해지면 별도로 만들어야 함).
- `GET /users/me` 응답에 `is_guest: true/false`가 있어서, 지금 세션이 게스트인지 프론트에서 구분할 수 있습니다.

### 1-1. (참고용) 회원가입 — 지금 프론트에서는 안 씀

```
POST /api/v1/auth/signup
{
  "email": "user@example.com",
  "password": "supersecret"   // 8~72자
}
```
→ `201`, 응답 바디는 로그인과 동일 (아래 참고). **회원가입하면 바로 로그인 상태가 됩니다** (토큰이 즉시 발급됨, 별도로 로그인 API를 다시 호출할 필요 없음).

### 1-2. 로그인

```
POST /api/v1/auth/login
{
  "email": "user@example.com",
  "password": "supersecret"
}
```
→ `200`
```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "s24movQYshi-OxPwyUELYaoZ6b4UQ_b1OdhGZWxGMA4",
  "token_type": "bearer"
}
```

- `access_token`: JWT. 기본 30분 후 만료. 인증이 필요한 모든 요청에 `Authorization: Bearer <access_token>` 헤더로 실어야 함.
- `refresh_token`: 랜덤 문자열. 기본 14일 유효. **한 번 쓰면 폐기되고 새 쌍이 발급됨(재사용 불가)** — 그래서 매번 refresh 응답으로 온 새 `refresh_token`으로 저장값을 덮어써야 합니다.
- 실패 시 `401 { "detail": "Invalid email or password" }`.
- 로그인/회원가입은 브루트포스 방지로 **분당 5회**로 제한되어 있음(`429` 참고).

### 1-3. 인증이 필요한 요청

```
GET /api/v1/users/me
Authorization: Bearer eyJhbGciOi...
```
- 토큰 없음/무효/만료: `401 { "detail": "Could not validate credentials" }`

### 1-4. Access token 만료 시 — refresh

```
POST /api/v1/auth/refresh
{ "refresh_token": "<저장해둔 refresh_token>" }
```
→ `200`, 로그인과 같은 형태로 **새 access_token + 새 refresh_token** 반환. 이전 refresh_token은 이제 못 씀.

권장 패턴: API 응답이 `401`이면 → refresh 호출 → 성공하면 새 access_token으로 원래 요청 재시도 → refresh도 실패하면 로그인 화면으로.

### 1-5. 로그아웃

```
POST /api/v1/auth/logout
{ "refresh_token": "<refresh_token>" }
```
→ `204`. 해당 refresh_token을 서버에서 폐기 (access_token은 만료 전까지는 계속 유효하니, 프론트에서도 즉시 버려야 함).

### 1-6. 내 정보 조회/수정

```
GET /api/v1/users/me                       → { id, email, created_at, is_guest }
PATCH /api/v1/users/me
{
  "email": "new@example.com",       // 선택
  "password": "newpassword",        // 선택
  "current_password": "supersecret" // email/password 바꿀 때 필수
}
```
- `email`/`password` 중 하나라도 바꾸려면 `current_password`가 반드시 있어야 함 (없으면 `422`).
- 비밀번호 틀리면 `401`. 이메일이 이미 다른 계정 소유면 `409`.

## 2. 공통 에러 규칙

| 상황 | 상태코드 | 바디 |
|---|---|---|
| 입력값 검증 실패 (Pydantic) | 422 | `{ "detail": [{"loc": [...], "msg": "...", "type": "..."}] }` (**배열**) |
| 일반 에러 (로그인 실패, 404 등) | 401/404/409/400/500/502 | `{ "detail": "에러 메시지 문자열" }` (**문자열**) |
| 레이트리밋 초과 | 429 | `{ "error": "Rate limit exceeded: ..." }` ⚠️ **키가 `detail`이 아니라 `error`** |

422와 나머지는 `detail`의 타입(배열 vs 문자열)이 다르니, 프론트 에러 파싱 시 구분해서 처리해야 합니다. 429만 키 자체가 다릅니다.

다른 사용자 소유의 리소스에 접근하면 (예: 남의 quiz_id로 조회) `403`이 아니라 **`404`**로 응답합니다 (리소스 존재 여부 자체를 숨김).

## 3. 기능별 엔드포인트

전부 `Authorization: Bearer <access_token>` 필요 (아래 표에 별도 표기 없으면 전부 필수).

### 3-1. 학습 채팅 (`/api/v1/study/sessions`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/study/sessions` | `{ "title": "...", "model"?: "qwen2.5:3b" }` → 세션 생성 |
| GET | `/study/sessions` | 내 세션 목록 |
| GET | `/study/sessions/{id}` | 세션 상세 + 메시지 히스토리 |
| DELETE | `/study/sessions/{id}` | 세션 삭제 → `204` |
| POST | `/study/sessions/{id}/messages` | `{ "content": "..." }` → `{ user_message, assistant_message }` |

메시지 전송은 LLM 호출이라 레이트리밋(`chat_rate_limit`, 기본 분당 10회) 적용됨.

### 3-2. 퀴즈 (`/api/v1/quizzes`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/quizzes` | 생성 (아래 참고) |
| GET | `/quizzes` | 목록 |
| GET | `/quizzes/{id}` | 상세 — **정답/해설 미노출** |
| POST | `/quizzes/{id}/submit` | 답안 제출 → 채점 |
| GET | `/quizzes/{id}/result` | 마지막 제출 결과 재조회 |

생성 요청:
```json
{
  "title": "OS 퀴즈",
  "study_session_id": "uuid",   // 이거 또는 source_text 중 하나만
  "source_text": null,
  "question_count": 5,           // 생략 시 기본 5, 최대 20
  "model": "qwen2.5:3b"
}
```
`study_session_id`와 `source_text`를 동시에 넣거나 둘 다 안 넣으면 `422`. AI 생성 실패 시 `502`.

문제 목록(`GET /quizzes/{id}`)의 각 문항:
```json
{ "id": "uuid", "order_index": 0, "question_text": "...", "choices": ["A","B","C","D"] }
```
제출:
```json
{ "answers": [{ "question_id": "uuid", "selected_index": 1 }, ...] }
```
— **모든 문항에 정확히 한 번씩** 답해야 함 (누락/중복 시 `400`). 결과 응답엔 `correct_answer`/`explanation`이 포함됨.

### 3-3. 면접 연습 (`/api/v1/interview/practice-sessions`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/interview/practice-sessions` | `{ "topic": "백엔드 개발자", "model"?: ... }` → 생성, 첫 질문 자동 포함 |
| GET | `/interview/practice-sessions` | 목록 |
| GET | `/interview/practice-sessions/{id}` | 상세 (질문/답변/피드백 turns 배열) |
| POST | `/interview/practice-sessions/{id}/answers` | `{ "answer": "..." }` → 피드백 + 다음 질문 |
| POST | `/interview/practice-sessions/{id}/complete` | 종료 → 종합 피드백 생성 |

답변 응답:
```json
{
  "answered_turn": { "id", "order_index", "question", "answer", "feedback", "created_at" },
  "next_turn": { ... } | null   // null이면 질문 다 썼다는 뜻, /complete 호출해야 함
}
```
- 이미 종료된 세션에 답변 제출/재종료 시도 → `409`
- 답변할 질문이 없는데 제출 → `409`
- 한 번도 답 안 하고 `/complete` 호출 → `400`

### 3-4. 면접 복기 (`/api/v1/interview/reviews`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/interview/reviews` | `{ company, position, interview_date(YYYY-MM-DD), content, model? }` → 생성 시 AI 피드백 즉시 생성 |
| GET | `/interview/reviews` | 목록 |
| GET | `/interview/reviews/{id}` | 상세 |
| PATCH | `/interview/reviews/{id}` | 부분 수정. **`content`를 실제로 바꿀 때만 피드백 재생성** (company/position/date만 바꾸면 기존 피드백 유지) |
| DELETE | `/interview/reviews/{id}` | 삭제 → `204` |

### 3-5. (참고) 범용 Ollama 프록시 `/api/v1/chat`

이건 JWT가 아니라 `X-API-Key` 헤더로 별도 인증합니다 (`API_KEY` 환경변수 미설정 시 인증 없음). 위 4개 기능과 무관한 초기 프로토타입용 엔드포인트라, 신규 프론트 연동에서는 안 쓰는 걸 추천합니다.

## 4. 헬스체크 (인증 불필요, 버전 프리픽스 없음)

- `GET /health` — 프로세스 생존 확인
- `GET /health/ready` — DB 연결까지 확인 (안 되면 `503`)

## 5. 최소 구현 순서 제안

프론트는 로그인 UI를 만들 계획이 없으므로, 이 순서로 만드시면 됩니다:

1. 앱 시작 시 `localStorage`에 토큰이 있는지 확인 → 없으면 `/auth/guest` 호출해서 저장, 있으면 그대로 재사용
2. 모든 API 호출에 `Authorization` 헤더 붙이는 공통 fetch 래퍼 작성
3. 그 래퍼에 401 감지 → refresh → 재시도 로직 넣기 (refresh도 실패하면 `/auth/guest`로 새 게스트 발급 — 이 경우 이전 데이터는 못 씀)
4. 그 다음에 실제 기능(학습챗/퀴즈/면접연습/면접복기) 화면 붙이기

회원가입/로그인 폼은 지금 당장은 필요 없습니다 (1-0 참고). 나중에 실제 계정 시스템이 필요해지면 그때 `/auth/signup`, `/auth/login`을 붙이면 됩니다 (엔드포인트는 이미 준비되어 있음).

토큰 저장을 `localStorage`에 하면 XSS 시 탈취 위험이 있다는 점만 참고해두세요(이 프로젝트 규모에서는 흔히 쓰는 트레이드오프입니다 — 더 안전하게 하려면 메모리 저장 + refresh는 짧은 수명의 httpOnly 쿠키로 가는 방법도 있는데, 그러려면 백엔드도 CSRF 대응이 추가로 필요해집니다).
