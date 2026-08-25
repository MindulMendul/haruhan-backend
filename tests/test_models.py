import asyncio

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    async def list_models(self):
        return [
            {
                "name": "qwen2.5:3b",
                "model": "qwen2.5:3b",
                "size": 1929601456,
                "details": {"parameter_size": "3.1B", "quantization_level": "Q4_0"},
            },
            {
                "name": "nomic-embed-text:latest",
                "model": "nomic-embed-text:latest",
                "size": 274302450,
                "details": {},
            },
        ]


class FailingOllamaService:
    async def list_models(self):
        raise OllamaServiceError("boom")


def test_list_models_returns_mapped_fields(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()

    response = client.get("/api/v1/models")
    assert response.status_code == 200
    body = response.json()
    assert len(body["models"]) == 2
    assert body["models"][0] == {
        "name": "qwen2.5:3b",
        "size": 1929601456,
        "parameter_size": "3.1B",
        "quantization_level": "Q4_0",
    }
    assert body["models"][1]["name"] == "nomic-embed-text:latest"
    assert body["models"][1]["parameter_size"] is None


def test_list_models_requires_no_auth(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()

    response = client.get("/api/v1/models")
    assert response.status_code == 200


def test_list_models_returns_502_on_ollama_failure(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()

    response = client.get("/api/v1/models")
    assert response.status_code == 502


def test_list_models_caches_result_within_ttl(client):
    class CountingOllamaService:
        def __init__(self):
            self.call_count = 0

        async def list_models(self):
            self.call_count += 1
            return [{"name": f"model-{self.call_count}", "size": 1}]

    fake = CountingOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake

    first = client.get("/api/v1/models")
    second = client.get("/api/v1/models")

    assert fake.call_count == 1
    assert first.json() == second.json()
    assert first.json()["models"][0]["name"] == "model-1"


def test_list_models_is_rate_limited(client, monkeypatch):
    """이 앱에서 유일하게 인증 없이 공개된 엔드포인트라, 레이트리밋이 없으면
    익명 호출자가 원하는 만큼 반복 호출할 수 있었다."""
    monkeypatch.setenv("MODELS_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()

    first = client.get("/api/v1/models")
    second = client.get("/api/v1/models")
    third = client.get("/api/v1/models")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_get_or_fetch_models_coalesces_concurrent_cache_misses():
    """캐시가 막 만료된 순간 동시에 들어온 요청들은 락 없이는 각자 독립적으로
    Ollama를 호출한다(캐시가 있는 의미가 없어짐) - 여러 호출자가 캐시가 비어있는
    상태에서 동시에 진입해도 실제 Ollama 호출은 정확히 한 번만 일어나고, 나머지는
    그 결과를 그대로 받아가는지 확인한다."""
    from app.api.v1.routes.models import _get_or_fetch_models, _models_cache

    class SlowCountingOllamaService:
        def __init__(self):
            self.call_count = 0

        async def list_models(self):
            self.call_count += 1
            # 캐시 미스 상태에서 여러 호출이 겹칠 시간을 벌어준다 - 이 sleep
            # 동안 락 없이 진입한 다른 호출들이 각자 이 메서드를 또 부르는지가
            # 이 테스트가 확인하려는 지점이다.
            await asyncio.sleep(0.05)
            return [{"name": "model-1", "size": 1}]

    fake = SlowCountingOllamaService()
    _models_cache.clear()

    async def _run():
        return await asyncio.gather(*[_get_or_fetch_models(fake) for _ in range(5)])

    results = asyncio.run(_run())

    assert fake.call_count == 1
    assert all(r == results[0] for r in results)
    assert results[0].models[0].name == "model-1"
