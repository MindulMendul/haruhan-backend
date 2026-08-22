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
- 나중에 진짜 회원가입/로그인 UI를 붙이고 싶으면, 기존 데이터를 그대로 유지한 채 실계정으로 전환하는 API가 있습니다 → 아래 1-0-1 참고.
- `GET /users/me` 응답에 `is_guest: true/false`가 있어서, 지금 세션이 게스트인지 프론트에서 구분할 수 있습니다.

### 1-0-1. 게스트 → 실계정 전환 (데이터 유지)

지금 로그인한 게스트에게 email/password를 등록해서, **같은 계정(같은 데이터)을 그대로 유지한 채** 실계정으로 승격시킵니다. access token은 그대로 유효하니 새로 로그인할 필요 없습니다.

```
POST /api/v1/users/me/upgrade
Authorization: Bearer <게스트 access_token>
{
  "email": "user@example.com",
  "password": "supersecret"   // 8~72자
}
```
→ `200`, `GET /users/me`와 같은 모양 (`is_guest`는 이제 `false`)
```json
{ "id": "...", "email": "user@example.com", "created_at": "...", "is_guest": false }
```

- 이미 실계정인 사용자가 호출하면 `409` (`current_password` 확인이 필요한 1-6의 `PATCH /users/me`를 대신 써야 함).
- 요청한 email이 이미 다른 계정 소유면 `409`.
- 승격 후에도 `POST /api/v1/auth/login`으로 방금 설정한 email/password로 로그인 가능.

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
- 실패 시 `401 { "error": { "code": "invalid_credentials", "message": "Invalid email or password" } }`.
- 로그인/회원가입은 브루트포스 방지로 **분당 5회**로 제한되어 있음(`429` 참고).

### 1-3. 인증이 필요한 요청

```
GET /api/v1/users/me
Authorization: Bearer eyJhbGciOi...
```
- 토큰 없음/무효/만료: `401 { "error": { "code": "invalid_token", "message": "Could not validate credentials" } }`

### 1-4. Access token 만료 시 — refresh

```
POST /api/v1/auth/refresh
{ "refresh_token": "<저장해둔 refresh_token>" }
```
→ `200`, 로그인과 같은 형태로 **새 access_token + 새 refresh_token** 반환. 이전 refresh_token은 이제 못 씀.

권장 패턴: API 응답이 `401`이면 → refresh 호출 → 성공하면 새 access_token으로 원래 요청 재시도 → refresh도 실패하면 로그인 화면으로.

로그인/회원가입과 마찬가지로 **분당 5회**로 제한되어 있습니다(`429` 참고) - 재시도 로직을 짤 때 무한 루프가 되지 않도록 주의하세요.

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

### 1-7. 계정 삭제 (회원 탈퇴)

```
DELETE /api/v1/users/me
{
  "current_password": "supersecret" // 실계정만 필수, 게스트는 생략 가능
}
```
→ `204` — 계정과 연관된 모든 데이터(학습챗/퀴즈/면접연습/면접복기/RAG 색인 등)가 즉시 영구 삭제됩니다. 되돌릴 수 없으니 프론트에서 확인 다이얼로그를 꼭 넣어주세요. 실계정인데 `current_password`가 없거나 틀리면 `401`.

### 1-8. 세션 관리 (로그인된 기기 목록/강제 로그아웃)

```
GET /api/v1/auth/sessions              → [{ id, created_at, expires_at }, ...]
DELETE /api/v1/auth/sessions/{id}      → 204 (해당 세션만 로그아웃)
DELETE /api/v1/auth/sessions           → 204 (모든 기기에서 로그아웃)
```
- 여기서 "세션"은 폐기/만료되지 않은 refresh_token 하나를 의미합니다. "비밀번호를 변경한 다른 기기 전부 로그아웃시키기" 같은 UI에 씁니다.
- 이 API는 access_token으로 인증하기 때문에, 지금 로그인해 요청을 보내는 **이 기기가 목록의 몇 번째 항목인지는 알 수 없습니다** (refresh_token이 발급 당시의 access_token과 연결돼 있지 않음). 활성 세션 개수 확인, 특정/전체 세션 로그아웃 용도로만 쓰세요.
- 존재하지 않거나 이미 만료/폐기됐거나 다른 사람 소유인 `{id}`를 지우려 하면 `404`.
- `DELETE /api/v1/auth/sessions`(전체 로그아웃)를 호출하면 지금 쓰고 있는 refresh_token도 함께 폐기되니, 호출 직후 프론트에서도 로그인 화면으로 보내야 합니다.

## 2. 공통 에러 규칙

> ⚠️ **에러 응답 포맷이 바뀌었습니다.** 예전에는 `{ "detail": "..." }`였는데, 지금은
> 아래처럼 `{ "error": { "code": "...", "message": "..." } }`로 통일됩니다. 기존에
> `detail` 필드를 파싱하던 프론트 코드는 `error.code`/`error.message`로 옮겨야
> 합니다.

| 상황 | 상태코드 | 바디 |
|---|---|---|
| 일반 에러 (로그인 실패, 404 등) | 401/404/409/400/500/502 | `{ "error": { "code": "invalid_credentials", "message": "..." } }` |
| 입력값 검증 실패 (Pydantic) | 422 | `{ "error": { "code": "validation_error", "message": "...", "details": [{"loc": [...], "msg": "...", "type": "..."}] } }` |
| 레이트리밋 초과 | 429 | `{ "error": { "code": "rate_limited", "message": "Rate limit exceeded: ..." } }` |

`error.code`는 프론트가 문자열 매칭 없이 에러 종류를 분기할 때 씁니다. 로그인 실패(`invalid_credentials`), 만료/위조된 access token(`invalid_token`), 재사용된 refresh token(`invalid_refresh_token`)처럼 자주 분기해야 하는 케이스부터 구체적인 code를 붙여뒀고, 아직 안 붙은 나머지는 상태코드 기반 기본값(`not_found`, `conflict`, `bad_request`, `internal_error` 등)이 들어갑니다 - 점진적으로 늘려나가는 중이라 오늘 `not_found`였던 에러가 나중에 더 구체적인 code로 바뀔 수 있습니다. 코드로 분기하되, `message`는 사용자에게 보여줄 최종 문구로 쓰지 말고 참고용으로만 쓰세요 (한글/영어가 섞여 있고 국제화 대상이 아닙니다).

레이트리밋이 걸린 엔드포인트(로그인/회원가입/토큰 refresh·로그아웃/프로필수정/학습챗·퀴즈·면접 생성 등)는 **성공 응답에도** `X-RateLimit-Limit`/`X-RateLimit-Remaining`/`X-RateLimit-Reset` 헤더가 실립니다. 429 응답에는 추가로 `Retry-After`(재시도까지 남은 초)가 실리니, 카운트다운 UI를 만들 때 응답 바디를 파싱할 필요 없이 이 헤더만 읽으면 됩니다.

다른 사용자 소유의 리소스에 접근하면 (예: 남의 quiz_id로 조회) `403`이 아니라 **`404`**로 응답합니다 (리소스 존재 여부 자체를 숨김).

## 3. 기능별 엔드포인트

전부 `Authorization: Bearer <access_token>` 필요 (아래 표에 별도 표기 없으면 전부 필수).

### 3-1. 학습 채팅 (`/api/v1/study/sessions`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/study/sessions` | `{ "title": "...", "model"?: "qwen2.5:3b" }` → 세션 생성 |
| GET | `/study/sessions` | 내 세션 목록 (페이지네이션, 아래 참고) |
| GET | `/study/sessions/{id}` | 세션 상세 + 메시지 히스토리 |
| PATCH | `/study/sessions/{id}` | `{ "title": "새 제목" }` → 제목만 변경 |
| DELETE | `/study/sessions/{id}` | 세션 삭제 → `204` |
| POST | `/study/sessions/{id}/messages` | `{ "content": "..." }` → `{ user_message, assistant_message }` |

메시지 전송은 LLM 호출이라 레이트리밋(`chat_rate_limit`, 기본 분당 10회) 적용됨.

목록 조회는 `?limit=20&offset=0` 쿼리 파라미터를 받음(`limit` 기본 20, 최대 100). 응답 바디는
그대로 배열이고, 전체 개수는 `X-Total-Count` 응답 헤더로 옴 — 다음 페이지가 있는지는
`받은 개수 + offset < X-Total-Count`로 판단하면 됨.

#### 3-1-1. 스트리밍 응답 (WebSocket)

응답을 다 기다렸다가 한 번에 받는 대신, 토큰 단위로 실시간으로 받고 싶으면 이 엔드포인트를
쓰면 됨. 기존 `POST /study/sessions/{id}/messages`는 그대로 남아있고(하위호환), 이건 완전히
별도 경로.

```
WS /api/v1/study/sessions/{id}/stream?token=<access_token>
```

- 브라우저 WebSocket API는 커스텀 헤더를 못 보내서, `Authorization` 헤더 대신 **쿼리
  파라미터로 access token을 넘김**. 토큰이 없거나 무효하면 연결 자체가 거부됨(코드 1008).
- 연결되면 `{ "content": "..." }`를 JSON으로 보내면 됨 (REST 버전의 요청 바디와 동일).
- 서버는 순서대로 아래 이벤트들을 보냄:
  ```json
  { "type": "user_message", "data": { "id", "role": "user", "content", "created_at" } }
  { "type": "delta", "content": "토" }
  { "type": "delta", "content": "큰" }
  ...
  { "type": "done", "data": { "id", "role": "assistant", "content": "전체 답변", "created_at" } }
  ```
  `delta`를 이어붙이면 `done.data.content`와 같아짐 — 화면에는 delta가 올 때마다 이어붙여
  표시하고, `done`이 오면 그 메시지를 최종 확정된 것으로 취급하면 됨.
- 실패하면 `{ "type": "error", "detail": "..." }`가 오고, **연결은 끊기지 않음** — 같은
  세션에 대해 다시 `{ "content": "..." }`를 보내면 됨 (내 세션이 아니거나, content가
  비어있거나 너무 길면 이 형태로 옴).
- 같은 연결로 여러 메시지를 계속 보낼 수 있음 (한 번 연결하면 세션 하나에 대해 대화 계속
  가능). 연결을 끊고 싶으면 그냥 소켓을 닫으면 됨.
- REST 엔드포인트와 같은 `CHAT_RATE_LIMIT`(기본 10/minute, IP 기준)이 이 경로에도
  독립적으로 적용됩니다 (REST 쪽 카운트와는 별도 버킷). 초과하면 연결이 끊기지 않고
  `{ "type": "error", "detail": "...", "retry_after": <초> }`가 옴 - `retry_after`초
  뒤에 다시 보내면 됨.

### 3-2. 퀴즈 (`/api/v1/quizzes`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/quizzes` | 생성 (아래 참고) |
| GET | `/quizzes` | 내 퀴즈 목록 (페이지네이션, 3-1과 동일한 방식) |
| GET | `/quizzes/{id}` | 상세 — **정답/해설 미노출** |
| PATCH | `/quizzes/{id}` | `{ "title": "새 제목" }` → 제목만 변경 |
| POST | `/quizzes/{id}/submit` | 답안 제출 → 채점 |
| GET | `/quizzes/{id}/result` | 마지막 제출 결과 재조회 |
| GET | `/quizzes/{id}/attempts` | 재도전 이력 전체 (아래 참고) |
| DELETE | `/quizzes/{id}` | 퀴즈 삭제 → `204` (문항/제출 이력도 함께 삭제) |
| GET | `/quizzes/wrong-answers` | 오답노트 (아래 참고) |

목록 조회는 3-1(학습 채팅)과 동일하게 `?limit=20&offset=0` 쿼리 파라미터를 받고(`limit` 기본 20, 최대 100), 전체 개수는 `X-Total-Count` 응답 헤더로 옵니다.

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

네트워크 재시도 등으로 같은 제출 요청이 두 번 가는 경우를 대비해, **직전 제출과 답안이 완전히 같고 5초 안에 다시 들어오면** 새로 채점하지 않고 직전 결과를 그대로 돌려줍니다 (같은 `attempt_id`). 실제로 다시 풀어서 답이 달라지면(또는 5초가 지나면) 정상적으로 새 시도로 기록됩니다 - 프론트에서 별도로 중복 제출 방지 로직을 넣지 않아도 됩니다.

#### 3-2-1. 재도전 이력

```
GET /api/v1/quizzes/{id}/attempts
```
→ `200`
```json
[
  { "id": "uuid", "score": 4, "total": 5, "submitted_at": "2026-08-21T12:00:00Z" },
  { "id": "uuid", "score": 3, "total": 5, "submitted_at": "2026-08-20T09:00:00Z" }
]
```
같은 퀴즈를 여러 번 다시 풀었을 때 **전체 제출 이력을 최신순**으로 돌려줍니다 (점수 추이 그래프 등에 사용). `GET /quizzes/{id}/result`는 가장 최근 1건의 문항별 정답 여부까지 상세히 주는 반면, 이건 점수 요약만 가볍게 줍니다. 아직 한 번도 제출 안 했다면 빈 배열, 존재하지 않거나 남의 퀴즈면 `404`.

#### 3-2-2. 오답노트

```
GET /api/v1/quizzes/wrong-answers
```
→ `200`
```json
{
  "entries": [
    {
      "quiz_id": "uuid", "quiz_title": "OS 퀴즈",
      "question_id": "uuid", "question_text": "...", "choices": ["A","B","C","D"],
      "selected_index": 0, "correct_answer": "B", "explanation": "..."
    }
  ]
}
```
내가 만든 모든 퀴즈를 통틀어, **퀴즈별 가장 최근 제출 기준**으로 틀린 문제만 모아서 보여줍니다. 같은 퀴즈를 다시 풀어서 맞히면 그 문제는 오답노트에서 바로 빠집니다. 별도 페이지네이션은 없음(개인 학습 데이터라 규모가 크지 않을 거라 가정).

### 3-3. 면접 연습 (`/api/v1/interview/practice-sessions`)

| Method | Path | 설명 |
|---|---|---|
| POST | `/interview/practice-sessions` | `{ "topic": "백엔드 개발자", "model"?: ... }` → 생성, 첫 질문 자동 포함 |
| GET | `/interview/practice-sessions` | 내 세션 목록 (페이지네이션, 아래 참고) |
| GET | `/interview/practice-sessions/{id}` | 상세 (질문/답변/피드백 turns 배열) |
| DELETE | `/interview/practice-sessions/{id}` | 세션 삭제 → `204` (문답 turns도 함께 삭제) |
| POST | `/interview/practice-sessions/{id}/answers` | `{ "answer": "..." }` → 피드백 + 다음 질문 |
| POST | `/interview/practice-sessions/{id}/complete` | 종료 → 종합 피드백 생성 |

목록 조회는 3-1(학습 채팅)과 동일한 방식으로 `?limit=20&offset=0` 쿼리 파라미터를 받고(`limit` 기본 20, 최대 100), 전체 개수는 `X-Total-Count` 응답 헤더로 옵니다.

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
| GET | `/interview/reviews` | 목록 (페이지네이션, 3-1과 동일한 방식) |
| GET | `/interview/reviews/{id}` | 상세 |
| PATCH | `/interview/reviews/{id}` | 부분 수정. **`content`를 실제로 바꿀 때만 피드백 재생성** (company/position/date만 바꾸면 기존 피드백 유지) |
| DELETE | `/interview/reviews/{id}` | 삭제 → `204` |

#### 3-4-1. 생성 스트리밍 응답 (WebSocket)

면접복기 AI 피드백은 복기 내용 전체를 분석해서 만들기 때문에 이 앱에서 가장 오래
걸리는 생성입니다. 응답을 다 기다리지 않고 토큰 단위로 받고 싶으면 이 엔드포인트를
쓰면 됩니다. 기존 `POST /interview/reviews`는 그대로 남아있음(하위호환) - PATCH(수정
시 피드백 재생성)는 스트리밍 버전이 없고 여전히 REST만 있습니다.

```
WS /api/v1/interview/reviews/stream?token=<access_token>
```

- 인증 방식은 3-1-1과 동일(쿼리 파라미터로 access token).
- 연결되면 `POST /interview/reviews`와 같은 바디(`{ company, position,
  interview_date, content, model? }`)를 JSON으로 보내면 됩니다.
- 서버는 순서대로:
  ```json
  { "type": "delta", "content": "잘" }
  { "type": "delta", "content": "한" }
  ...
  { "type": "done", "data": { "id", "company", "position", "interview_date", "content", "ai_feedback", "created_at", "updated_at" } }
  ```
  `user_message` 같은 중간 echo 이벤트는 없습니다 - 피드백 생성이 끝나야 review
  자체가 만들어지기 때문입니다. `done.data.ai_feedback`이 delta를 이어붙인 값과
  같습니다.
- 검증 실패(필드 누락 등)나 생성 실패는 `{ "type": "error", "detail": "..." }`가
  오고 연결은 끊기지 않습니다. `CHAT_RATE_LIMIT` 초과 시에도 마찬가지로
  `retry_after`가 포함된 에러 이벤트가 옵니다(3-1-1과 동일).
- 같은 연결로 여러 건을 연달아 생성할 수 있습니다.

### 3-5. (참고) 범용 Ollama 프록시 `/api/v1/chat`

이건 JWT가 아니라 `X-API-Key` 헤더로 별도 인증합니다 (`API_KEY` 환경변수 미설정 시 인증 없음). 위 4개 기능과 무관한 초기 프로토타입용 엔드포인트라, 신규 프론트 연동에서는 안 쓰는 걸 추천합니다.

### 3-6. 사용 가능한 모델 목록 `/api/v1/models`

```
GET /api/v1/models   (인증 불필요)
```
→ `200`
```json
{
  "models": [
    { "name": "qwen2.5:3b", "size": 1929601456, "parameter_size": "3.1B", "quantization_level": "Q4_0" },
    { "name": "nomic-embed-text:latest", "size": 274302450, "parameter_size": null, "quantization_level": null }
  ]
}
```
학습챗/퀴즈/면접연습/면접복기 생성 시 넘기는 `model` 필드를 하드코딩하지 말고, 여기서 받은 `name` 중 하나를 쓰면 됩니다. Ollama 엔진 자체가 응답을 못 하면 `502`. 서버가 응답을 60초간 캐시하므로, 새 모델을 pull한 직후에는 최대 60초 정도 반영이 늦을 수 있습니다.

### 3-7. 내 데이터 내보내기 `/api/v1/export/me`

```
GET /api/v1/export/me   (인증 필요)
```
→ `200`
```json
{
  "exported_at": "2026-01-01T00:00:00",
  "user_id": "...",
  "study_sessions": [ { "id": "...", "title": "...", "model": "...", "created_at": "...", "updated_at": "...", "messages": [ { "id": "...", "role": "user", "content": "...", "created_at": "..." } ] } ],
  "quizzes": [ { "id": "...", "title": "...", "source_study_session_id": null, "created_at": "...", "questions": [ { "id": "...", "order_index": 0, "question_text": "...", "choices": ["..."], "correct_answer": "...", "explanation": "..." } ], "attempts": [ { "id": "...", "score": 1, "total": 1, "submitted_at": "...", "answers": [ { "id": "...", "question_id": "...", "selected_index": 0, "is_correct": true } ] } ] } ],
  "interview_practice_sessions": [ { "id": "...", "topic": "...", "model": "...", "status": "completed", "overall_feedback": null, "created_at": "...", "updated_at": "...", "turns": [ { "id": "...", "order_index": 0, "question": "...", "answer": null, "feedback": null, "created_at": "..." } ] } ],
  "interview_reviews": [ { "id": "...", "company": "...", "position": "...", "interview_date": "2026-01-01", "content": "...", "model": "...", "ai_feedback": null, "created_at": "...", "updated_at": "..." } ]
}
```
본인 소유 기록 전체를 한 번에 JSON으로 내려받습니다. 퀴즈 문제에는 (풀이용 목록 조회와 달리) `correct_answer`/`explanation`이 그대로 포함됩니다. 파일 다운로드로 만들고 싶으면 프론트에서 이 응답을 그대로 Blob으로 감싸서 저장하면 됩니다 (서버가 `Content-Disposition`을 붙여주진 않음).

## 4. 헬스체크/메트릭 (인증 불필요, 버전 프리픽스 없음)

- `GET /health` — 프로세스 생존 확인
- `GET /health/ready` — DB/Redis/Ollama 연결까지 확인. 응답 바디에 `database`/`redis`/`ollama` 각각의 상태가 들어있어서 뭐가 죽었는지 바로 구분할 수 있습니다 (`redis`는 `REDIS_URL` 미설정 시 `not_configured`로 표시되고 전체 판정에서 제외됨). 하나라도 문제면 `503`.
- `GET /metrics` — Prometheus 스크레이프용. 프론트에서 호출할 일은 없습니다.

## 5. 최소 구현 순서 제안

프론트는 로그인 UI를 만들 계획이 없으므로, 이 순서로 만드시면 됩니다:

1. 앱 시작 시 `localStorage`에 토큰이 있는지 확인 → 없으면 `/auth/guest` 호출해서 저장, 있으면 그대로 재사용
2. 모든 API 호출에 `Authorization` 헤더 붙이는 공통 fetch 래퍼 작성
3. 그 래퍼에 401 감지 → refresh → 재시도 로직 넣기 (refresh도 실패하면 `/auth/guest`로 새 게스트 발급 — 이 경우 이전 데이터는 못 씀)
4. 그 다음에 실제 기능(학습챗/퀴즈/면접연습/면접복기) 화면 붙이기

회원가입/로그인 폼은 지금 당장은 필요 없습니다 (1-0 참고). 나중에 실제 계정 시스템이 필요해지면 그때 `/auth/signup`, `/auth/login`을 붙이면 됩니다 (엔드포인트는 이미 준비되어 있음).

토큰 저장을 `localStorage`에 하면 XSS 시 탈취 위험이 있다는 점만 참고해두세요(이 프로젝트 규모에서는 흔히 쓰는 트레이드오프입니다 — 더 안전하게 하려면 메모리 저장 + refresh는 짧은 수명의 httpOnly 쿠키로 가는 방법도 있는데, 그러려면 백엔드도 CSRF 대응이 추가로 필요해집니다).
