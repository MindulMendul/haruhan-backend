import asyncio
import logging
import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.services.ollama_service import OllamaService, OllamaServiceError

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _rank_top_k(
    query_embedding: list[float], candidates: list[tuple[list[float], str]], top_k: int
) -> list[str]:
    """사용자가 오래 쓸수록 색인된 청크 수는 계속 늘어나기만 하는데(만료/정리
    없음), retrieve_relevant는 매 학습챗 메시지/면접연습 턴마다 후보 전체를
    코사인 유사도로 채점한다 - 후보가 많아지면 이 채점 자체가 무시 못 할
    CPU 작업이 되는데, 예전엔 이걸 이벤트 루프에서 그대로(await 없이) 돌려서
    그 시간만큼 같은 워커의 다른 모든 동시 요청이 멈췄다. 세션/ORM 객체가
    아니라 이미 로드된 (embedding, content) 순수 데이터만 넘겨받아, 이벤트
    루프와 무관한 스레드 풀에서 계산해도 안전하게 만들었다."""
    scored = []
    for embedding, content in candidates:
        if len(embedding) != len(query_embedding):
            # list_for_user()는 embedding_model "문자열"만 같은 후보를
            # 걸러줄 뿐, 실제 벡터 길이가 같다는 보장은 아무 데도 없다 -
            # 같은 태그의 모델이 다른 차원으로 재배포되거나 EMBEDDING_MODEL
            # 설정이 기존 색인 재생성 없이 바뀌면 차원이 다른 벡터끼리
            # 섞일 수 있다. _cosine_similarity()의 zip(a, b)는 짧은 쪽에
            # 맞춰 조용히 자르는데, norm은 원래 길이 그대로 계산되므로
            # 비교 불가능한 두 벡터가 우연히 완벽한 점수(1.0)로 채점돼
            # 실제로 관련 있는 기록을 밀어내고 1등을 차지하는 것까지
            # 실제로 재현해 확인했다 - 조용히 틀린 순위를 만드는 대신
            # 비교 불가능한 후보는 채점에서 아예 제외한다.
            logger.warning(
                "RAG 검색에서 차원이 다른 임베딩 건너뜀: query_dim=%d chunk_dim=%d",
                len(query_embedding),
                len(embedding),
            )
            continue
        scored.append((_cosine_similarity(query_embedding, embedding), content))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [content for _, content in scored[:top_k]]


class RagService:
    """사용자 본인의 기존 기록(학습챗/면접복기)을 색인하고, 새 질문과 의미적으로
    가까운 기록을 검색해 학습챗 그라운딩에 쓴다."""

    def __init__(self, session: AsyncSession, ollama_service: OllamaService, settings: Settings) -> None:
        self._session = session
        self._chunks = KnowledgeChunkRepository(session)
        self._ollama = ollama_service
        self._settings = settings

    async def _safe_commit(self, log_context: str, is_final_session_use: bool) -> None:
        """198라운드: index_content/forget_content(_bulk)가 delete_for_source()/
        _chunks.create() 같은 개별 쿼리는 SAVEPOINT(begin_nested())로 감싸 실패해도
        세션의 다른 객체를 expire시키지 않도록 고쳤지만(retrieve_relevant()
        docstring 참고), commit() 자체가 실패하는 경우는(진짜 커밋 시점의 DB 오류)
        SAVEPOINT로 격리할 수 없다 - 이미 앞선 SAVEPOINT가 flush를 끝내둔 뒤라
        보통 이 commit()은 새로 flush할 게 없는 순수한 COMMIT 실행 자체만 실패하는
        경우다.

        199라운드: 이 commit()이 실패하면 SQLAlchemy는 세션을 "prepared" 상태로
        남겨(다음 쿼리를 시도하면 즉시 InvalidRequestError) rollback() 없이는
        세션 자체를 더 못 쓰게 만든다는 것까지 확인했다 - 그런데 그 rollback()은
        198라운드가 고친 것과 정확히 같은 부작용(이 세션에 이미 로드된, 이
        메서드와 무관한 다른 객체까지 전부 expire시킴)을 낸다. 재현 스크립트로
        직접 확인한 결과: (1) 이 commit() 실패 자체는 rollback() 전까지 아무것도
        expire시키지 않는다, (2) rollback()을 부르지 않고 그냥 두면 세션은
        "prepared" 상태로 남지만 이미 로드된 객체의 속성 읽기는 여전히 멀쩡히
        동작한다(추가 쿼리가 필요 없으므로), (3) 이 세션을 나중에 close()할 때도
        rollback()을 먼저 부를 필요가 없다(SQLAlchemy가 알아서 커넥션을 풀에
        정상적으로 반납함, 커넥션 누수 없음).

        즉 "이 세션으로 더 할 일이 없는"(is_final_session_use=True) 호출부에서는
        rollback()을 아예 안 불러서 다른 객체의 expire 자체를 막을 수 있다 -
        study_service.send_message/interview_review_service.create_review 같은
        REST 한 번짜리 요청들이 여기 해당한다(색인은 항상 그 요청의 마지막
        DB 작업이라 이후 이 세션으로 아무 쿼리도 안 함, 라우트는 이미 로드된
        ORM 객체의 속성만 읽어 Pydantic으로 직렬화함). 반면 학습챗/면접복기
        WebSocket 스트리밍(study_service.stream_message/interview_review_
        service.stream_create_review)은 연결 하나가 여러 메시지 동안 같은
        세션을 계속 재사용한다 - 이번 메시지의 색인이 이 commit()에서 실패한
        채로 rollback() 없이 넘어가면, 세션이 "prepared" 상태로 남아 다음
        메시지가 이 세션으로 쿼리를 하나만 날려도 InvalidRequestError로 죽는다
        (RAG 실패 하나가 그 이후 전체 WS 연결을 조용히 망가뜨림 - 이 메서드가
        원래 막으려던 것보다 더 나쁜 결과). rag_backfill_service.py의 예약
        작업도 같은 이유로 세션 하나를 여러 색인 호출에 걸쳐 재사용해 위험하다
        - 그래서 이 두 부류는 is_final_session_use=False(기본값)로 둬서 항상
        rollback()해 세션을 다음 쿼리가 가능한 상태로 복구한다. 어느 쪽이든
        "어떤 이유로든 실패해도 조용히 건너뛴다"는 이 클래스의 원칙은 지킨다 -
        차이는 그 복구 방법(rollback 생략 vs rollback)뿐이다."""
        try:
            await self._session.commit()
        except Exception:
            logger.exception("RAG 부가 기능 커밋 실패 (예상 못한 DB 오류 - %s)", log_context)
            if not is_final_session_use:
                await self._session.rollback()

    async def index_content(
        self,
        user_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        content: str,
        is_final_session_use: bool = False,
    ) -> None:
        """레거시 데이터를 검색 대상으로 색인한다. 같은 source에 대한 기존 색인은 먼저 지운다.

        is_final_session_use: 이 호출 이후 호출부가(그리고 이 요청/작업이 끝날 때까지)
        같은 세션으로 더는 아무 쿼리도 안 하면 True를 넘긴다 - _safe_commit() docstring
        참고. 기본값(False)은 세션이 이어서 재사용될 수 있는 경우(WebSocket 스트리밍
        연결의 다음 메시지, rag_backfill_service의 다음 반복)를 위한 안전한 선택이다.

        색인은 부가 기능이라 어떤 이유로든(임베딩 호출 실패뿐 아니라 DB 오류까지) 실패해도
        조용히 건너뛴다 - 이 메서드는 항상 본 기능(채팅/복기 저장 등)이 이미 커밋된 "뒤"
        마지막 단계로 호출되므로, 여기서 잡지 못한 예외가 그대로 위로 전파되면 실제로는
        성공한 요청이 500으로 보여 클라이언트가 재시도하다 중복 리소스를 만들 위험이 있다.

        196라운드: retrieve_relevant()와 같은 이유로(그쪽 docstring 참고) 이 메서드도
        delete_for_source() 조회 직후, embed()(Ollama 호출) 전에 commit()해서 커넥션을
        풀에 돌려준다 - study_service.send_message가 AI 응답을 받은 뒤 호출하는 이
        메서드 자신이 delete_for_source()로 커넥션을 붙든 채 곧바로 embed()로 넘어가고
        있었다(파일 기반 SQLite 풀로 이 메서드를 직접 재현해 확인). 이 메서드는 항상
        본 기능이 이미 커밋된 뒤 호출되어(위 문단 참고) 이 시점에 남아있는 잠금이
        없으므로, retrieve_relevant()와 달리 release_connection 같은 조건부 분기 없이
        항상 커밋해도 안전하다.

        198라운드: 예전엔 delete_for_source()/_chunks.create() 실패를 하나의 큰
        try/except가 묶어서 잡고 `await self._session.rollback()`으로 처리했는데,
        retrieve_relevant()의 같은 문제(그쪽 docstring 참고)와 정확히 같은 이유로
        위험하다 - 이 메서드는 항상 호출부가 본 기능을 이미 커밋한 "뒤"(위 문단
        참고) 같은 세션으로 불리므로, 그 세션엔 호출부가 로드해둔 assistant_
        message 등 이 메서드와 무관한 객체가 남아있다. rollback()은 그 객체들을
        전부 expire시켜서, 이 메서드가 조용히 실패를 삼키고 리턴해도 그 직후
        호출부(예: study_service.send_message가 곧바로 잇달아 부르는 두 번째
        index_content() 호출의 인자로 쓰는 assistant_message.id)가 그 expire된
        객체에 동기적으로 접근하는 순간 MissingGreenlet으로 죽는다 - "색인 실패는
        조용히 건너뛴다"는 이 메서드 자신의 약속과 반대로 본 기능이 이미 끝난
        뒤인데도 크래시가 나는 것까지 재현해 확인했다. delete_for_source()/
        _chunks.create() 각각을 SAVEPOINT(session.begin_nested())로 감싸 실패해도
        그 SAVEPOINT까지만 롤백되게 한다 - 이미 커밋된 이전 단계나 세션의 다른
        객체는 전혀 건드리지 않는다(retrieve_relevant()에서 별도 재현 스크립트로
        확인한 것과 같은 SAVEPOINT 동작).
        """
        try:
            async with self._session.begin_nested():
                await self._chunks.delete_for_source(source_type, source_id)
        except Exception:
            logger.exception(
                "RAG 색인 실패 (예상 못한 DB 오류 - 기존 색인 삭제): user_id=%s source_type=%s source_id=%s",
                user_id,
                source_type,
                source_id,
            )
            return

        if not content.strip():
            await self._safe_commit(f"index_content 빈 콘텐츠: source_id={source_id}", is_final_session_use)
            return

        await self._safe_commit(f"index_content 삭제: source_id={source_id}", is_final_session_use)

        model = self._settings.embedding_model
        try:
            embedding = await self._ollama.embed(text=content, model=model)
        except OllamaServiceError:
            logger.error(
                "RAG 색인 실패 (임베딩 호출 에러): user_id=%s source_type=%s source_id=%s",
                user_id,
                source_type,
                source_id,
            )
            await self._safe_commit(f"index_content 임베딩 실패: source_id={source_id}", is_final_session_use)
            return

        if embedding:
            try:
                async with self._session.begin_nested():
                    await self._chunks.create(
                        user_id=user_id,
                        source_type=source_type,
                        source_id=source_id,
                        content=content,
                        embedding=embedding,
                        embedding_model=model,
                    )
            except Exception:
                logger.exception(
                    "RAG 색인 실패 (예상 못한 DB 오류 - 색인 생성): user_id=%s source_type=%s source_id=%s",
                    user_id,
                    source_type,
                    source_id,
                )
                return
        else:
            logger.warning(
                "RAG 색인 건너뜀 (빈 임베딩 반환): user_id=%s source_type=%s source_id=%s",
                user_id,
                source_type,
                source_id,
            )
        await self._safe_commit(f"index_content 최종: source_id={source_id}", is_final_session_use)

    async def retrieve_relevant(
        self, user_id: uuid.UUID, query: str, release_connection: bool = True
    ) -> list[str]:
        """query와 의미적으로 가까운 사용자 본인의 기존 기록 상위 K개를 반환한다.

        검색 실패는 전부 빈 리스트로 처리한다 - RAG는 답변 품질을 보강하는 부가 기능이라
        실패해도 채팅 자체는 평소대로 계속되어야 한다. index_content/forget_content(_bulk)와
        같은 이유로, 임베딩 호출 실패(OllamaServiceError)뿐 아니라 이 메서드 자신의
        DB 조회(list_for_user)에서 나는 예상 못한 오류(커넥션 드롭, 스테이트먼트 타임아웃
        등)도 삼켜야 한다 - 여기서 안 잡으면 학습챗/면접연습의 모든 턴마다 도는 이
        "부가 기능" 조회 하나가 그대로 채팅 자체를 500(REST)/비정상 종료(WS)로 만들어버려,
        이 클래스의 다른 세 메서드가 지키는 "RAG 실패는 절대 본 기능을 막지 않는다"는
        약속이 정작 가장 자주 불리는 이 메서드에서만 깨져 있었다.

        193라운드가 study_service.send_message 등 세 호출부에 이 메서드가
        "돌아온 뒤" commit()을 추가했는데, 정작 이 메서드 자신도 list_for_user()
        조회 뒤 곧바로 embed()(Ollama HTTP 호출)로 넘어가면서 그 사이 커밋을
        한 번도 안 해 - 호출부의 그 수정과 별개로 - 이 메서드 안에서 이미 DB
        커넥션을 embed() 호출 내내 붙들고 있었다(파일 기반 SQLite 풀로 실제
        재현해 확인). candidates가 있어 embed()까지 실제로 가는 경우에만
        해당한다. release_connection=True(기본값)면 이 조회 직후 commit()해서
        embed() 동안 커넥션을 풀에 돌려준다 - study_service.send_message/
        stream_message, interview_practice_service.create_session처럼 이
        메서드를 부르는 시점에 잠금을 붙들고 있지 않은 호출부용이다.
        interview_practice_service.submit_answer/complete_session은 get_for_
        user_locked()의 FOR UPDATE 잠금을 AI 호출 전체(이 메서드 포함) 동안
        의도적으로 붙들고 있어야 하므로(그쪽 주석 참고) release_connection=
        False를 넘겨 이 메서드 안에서 조기에 커밋하지 않게 한다 - 그렇지
        않으면 그 잠금이 여기서 먼저 풀려 193라운드가 명시적으로 지키기로 한
        직렬화 트레이드오프가 깨진다.

        198라운드: list_for_user() 실패를 삼키는 이 except가 예전엔 `await
        self._session.rollback()`을 불렀는데, Session.rollback()은
        expire_on_commit 설정과 무관하게 이 세션에 이미 로드된 "이 메서드와
        전혀 무관한" 다른 객체까지 전부 expire시킨다(193라운드가 커넥션 해제에
        commit()을 쓰기로 한 것과 같은 SQLAlchemy 동작). 이 세션은 study_
        service.send_message의 study_session/user_message, interview_
        practice_service.submit_answer의 practice_session처럼 호출부가 이미
        로드해둔 객체를 그대로 공유하는데, list_for_user()가 (커넥션 드롭 등으로)
        실패해 여기서 rollback()하면 그 객체들이 expire되고, 바로 다음 줄에서
        (예: study_session.model처럼) 동기적으로 접근하는 순간 SQLAlchemy가
        MissingGreenlet으로 죽는다 - "RAG 실패는 본 기능을 막지 않는다"는 이
        메서드 자신의 약속과 정반대로, 부가 기능의 일시적 DB 오류가 본 기능을
        확실히 크래시시켰다(파일 기반 SQLite로 세션이 실제 트랜잭션을 문 상태에서
        list_for_user()가 실패하게 만들어 study_service.send_message가
        MissingGreenlet으로 죽는 것까지 재현해 확인했다). release_connection=
        False인 잠긴 호출부(submit_answer/complete_session)는 한술 더 떠
        rollback()이 이 트랜잭션 자체를 끝내버려 get_for_user_locked()의 FOR
        UPDATE 잠금까지 조기에 풀어버린다.

        session.rollback() 대신 이 조회 하나만 SAVEPOINT(session.begin_nested())로
        감싼다 - 실패하면 이 SAVEPOINT까지만 롤백되고 세션의 나머지 상태(이미
        로드된 다른 객체, 열려 있는 바깥 트랜잭션과 그 잠금)는 전혀 건드리지
        않는다는 것을 별도 재현 스크립트로 확인했다(SAVEPOINT 롤백 후에도
        loaded 객체의 expired 상태가 그대로 False로 유지되고, 같은 세션으로
        다른 조회도 문제없이 계속 됨).
        """
        model = self._settings.embedding_model
        try:
            async with self._session.begin_nested():
                candidates = await self._chunks.list_for_user(
                    user_id, embedding_model=model, limit=self._settings.rag_max_candidate_chunks
                )
        except Exception:
            logger.exception("RAG 검색 실패 (예상 못한 DB 오류): user_id=%s", user_id)
            return []
        if not candidates:
            return []

        if release_connection:
            await self._session.commit()

        try:
            query_embedding = await self._ollama.embed(text=query, model=model)
        except OllamaServiceError:
            logger.warning("RAG 검색 실패 (임베딩 호출 에러): user_id=%s", user_id)
            return []
        if not query_embedding:
            logger.warning("RAG 검색 건너뜀 (빈 임베딩 반환): user_id=%s", user_id)
            return []

        pairs = [(chunk.embedding, chunk.content) for chunk in candidates]
        try:
            return await asyncio.to_thread(_rank_top_k, query_embedding, pairs, self._settings.rag_top_k)
        except Exception:
            # list_for_user/embed 두 단계는 각자 예외를 이미 삼키는데, 이
            # 마지막 랭킹 단계만 아무 보호가 없었다 - 189라운드가 정리한
            # "이 메서드의 모든 단계가 예상 못한 오류를 삼켜야 한다"는
            # 원칙을 세 번째 단계에도 마저 적용한다.
            logger.exception("RAG 검색 실패 (예상 못한 랭킹 오류): user_id=%s", user_id)
            return []

    async def forget_content(
        self, source_type: str, source_id: uuid.UUID, is_final_session_use: bool = False
    ) -> None:
        """원본이 삭제될 때 색인도 함께 지운다.

        index_content와 같은 이유로 여기도 항상 원본(세션/복기 등)이 이미 커밋으로
        삭제된 "뒤" 호출되므로, 이 정리 단계에서 나는 예상 못한 DB 오류를 그대로
        전파하면 실제로는 성공한 삭제 요청이 500으로 보인다 - 조용히 삼키고 로그만
        남긴다.

        198라운드: delete_for_source()를 SAVEPOINT(begin_nested())로 감싸고
        commit()은 _safe_commit()으로 분리했다 - index_content()의 같은 수정과
        정확히 같은 이유(그쪽 docstring 참고)로, 예전 `await self._session.
        rollback()`이 이 세션에 호출부(예: study_session 삭제 요청)가 이미
        로드해둔 다른 객체까지 expire시켜 MissingGreenlet을 유발할 수 있었다.

        is_final_session_use: index_content()와 같은 의미(그쪽 docstring 참고) -
        commit() 자체가 실패했을 때 이 세션으로 더 할 일이 없으면 True를 넘긴다."""
        try:
            async with self._session.begin_nested():
                await self._chunks.delete_for_source(source_type, source_id)
        except Exception:
            logger.exception(
                "RAG 색인 정리 실패 (예상 못한 DB 오류 - 삭제): source_type=%s source_id=%s",
                source_type,
                source_id,
            )
            return
        await self._safe_commit(f"forget_content: source_id={source_id}", is_final_session_use)

    async def forget_content_bulk(
        self, source_type: str, source_ids: list[uuid.UUID], is_final_session_use: bool = False
    ) -> None:
        """forget_content의 배치 버전 - 세션/연습 하나를 지울 때 그 안의 메시지/턴
        전부를 한 번의 DELETE+commit으로 처리한다(호출부마다 반복 호출하지 않도록).
        예외 처리 이유는 forget_content와 동일(198라운드의 SAVEPOINT 분리 포함).
        is_final_session_use는 index_content()와 같은 의미(그쪽 docstring 참고)."""
        if not source_ids:
            return
        try:
            async with self._session.begin_nested():
                await self._chunks.delete_for_sources(source_type, source_ids)
        except Exception:
            logger.exception(
                "RAG 색인 일괄 정리 실패 (예상 못한 DB 오류 - 삭제): source_type=%s source_id_count=%d",
                source_type,
                len(source_ids),
            )
            return
        await self._safe_commit(f"forget_content_bulk: source_type={source_type}", is_final_session_use)
