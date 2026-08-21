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
