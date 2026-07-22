# 기여 가이드

## 브랜치 전략

- `main`은 항상 배포 가능한 상태를 유지합니다. `main`에 직접 커밋하지 않습니다.
- 작업 브랜치는 목적에 맞는 접두사를 사용합니다.
  - `feat/짧은-설명` — 새 기능
  - `fix/짧은-설명` — 버그 수정
  - `chore/짧은-설명` — 빌드/설정/의존성 등 잡무
  - `docs/짧은-설명` — 문서만 변경
  - `refactor/짧은-설명` — 동작 변경 없는 구조 개선

## 커밋 메시지 컨벤션

이 저장소는 [Conventional Commits](https://www.conventionalcommits.org/)를 따릅니다.

```
<type>: <설명>
```

- `feat`: 새 기능
- `fix`: 버그 수정
- `chore`: 빌드, 설정, 의존성 등 코드 동작에 영향 없는 변경
- `refactor`: 기능 변경 없는 코드 구조 개선
- `docs`: 문서 변경
- `test`: 테스트 추가/수정

예: `fix: use custom user-defined bridge network in docker-compose`

## PR 규칙

1. **하나의 PR은 하나의 목적만** 다룹니다. 관련 없는 변경을 섞지 않습니다.
2. PR을 열기 전에 로컬에서 `pytest`를 통과시킵니다.
3. PR 설명은 `.github/pull_request_template.md` 템플릿을 채워 작성합니다 (변경 내용/이유/테스트 방법 포함).
4. **CI(GitHub Actions)가 통과해야 머지 가능**합니다.
5. 협업자가 있는 경우 최소 1명의 리뷰 승인 후 머지합니다. 리뷰어가 없는 1인 개발 상황이라도, 머지 전에 PR diff를 한 번 더 스스로 검토합니다.
6. API 스펙, 환경 변수, 인증 방식 등 호출자에게 영향을 주는 변경은 PR 설명에 **Breaking Change**로 명시합니다.
7. `.env`, API 키, DB 접속 정보 등 민감 정보는 절대 커밋하지 않습니다. 새 환경 변수를 추가했다면 `.env.example`도 함께 갱신합니다.
8. 머지 방식은 커밋 히스토리를 깔끔하게 유지하기 위해 **Squash and merge**를 기본으로 합니다.

## 코드 스타일

- 레이어드 구조(`app/api`, `app/services`, `app/repositories`, `app/schemas`, `app/core`)를 유지합니다. 라우트 함수에 비즈니스 로직/DB 접근 코드를 직접 넣지 않습니다.
- 새 엔드포인트를 추가할 때는 인증(`verify_api_key` 등)과 레이트 리밋 적용 여부를 검토합니다.
- 외부 입력(요청 바디, 쿼리 파라미터)은 Pydantic 스키마로 검증합니다.

## 로컬 개발 환경

```bash
pip install -r requirements-dev.txt
cp .env.example .env  # 필요한 값 채우기
pytest -v
uvicorn app.main:app --reload
```
