import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.study_message import StudyMessage
from app.db.models.study_session import StudySession
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.services.ollama_service import OllamaService, OllamaServiceError

_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Study session not found"
)


class StudyService:
    def __init__(self, session: AsyncSession, ollama_service: OllamaService) -> None:
        self._session = session
        self._sessions = StudySessionRepository(session)
        self._messages = StudyMessageRepository(session)
        self._ollama = ollama_service

    async def create_session(self, user_id: uuid.UUID, title: str, model: str) -> StudySession:
        study_session = await self._sessions.create(user_id=user_id, title=title, model=model)
        await self._session.commit()
        return study_session

    async def list_sessions(self, user_id: uuid.UUID) -> list[StudySession]:
        return await self._sessions.list_for_user(user_id)

    async def get_session_with_messages(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[StudySession, list[StudyMessage]]:
        study_session = await self._sessions.get_for_user(session_id, user_id)
        if study_session is None:
            raise _SESSION_NOT_FOUND
        messages = await self._messages.list_for_session(session_id)
        return study_session, messages

    async def delete_session(self, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
        study_session = await self._sessions.get_for_user(session_id, user_id)
        if study_session is None:
            raise _SESSION_NOT_FOUND
        await self._sessions.delete(study_session)
        await self._session.commit()

    async def send_message(
        self, session_id: uuid.UUID, user_id: uuid.UUID, content: str
    ) -> tuple[StudyMessage, StudyMessage]:
        study_session = await self._sessions.get_for_user(session_id, user_id)
        if study_session is None:
            raise _SESSION_NOT_FOUND

        history = await self._messages.list_for_session(session_id)

        user_message = await self._messages.create(session_id=session_id, role="user", content=content)
        # AI 호출 성패와 무관하게 사용자가 입력한 메시지는 먼저 커밋해서 보존한다.
        await self._session.commit()

        chat_messages = [{"role": m.role, "content": m.content} for m in history]
        chat_messages.append({"role": "user", "content": content})

        try:
            reply = await self._ollama.chat(messages=chat_messages, model=study_session.model)
        except OllamaServiceError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

        assistant_message = await self._messages.create(
            session_id=session_id, role="assistant", content=reply
        )
        await self._sessions.touch(study_session)
        await self._session.commit()
        return user_message, assistant_message
