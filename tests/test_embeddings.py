import httpx

import app.services.embeddings as embeddings

MATRIX_A = [[0.0, 0.0], [0.0, 0.0]]
MATRIX_B = [[1.0, 1.0], [1.0, 1.0]]
MATRIX_C = [[2.0, 2.0], [2.0, 2.0]]


class FakeResponse:
    def __init__(self, status_code: int = 200, payload: object | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"status {self.status_code}", request=None, response=None
            )

    def json(self) -> object:
        return self._payload


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    async def post(self, url: str, json: dict[str, object]) -> FakeResponse:
        assert url == embeddings.HF_EMBEDDINGS_URL
        self.calls.append(json)
        return self._responses.pop(0)


def _patch(monkeypatch, client: FakeClient) -> None:
    monkeypatch.setattr(embeddings, "HF_TOKEN", "test-token")
    monkeypatch.setattr(embeddings, "_get_client", lambda: client)

    async def _noop_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(embeddings.asyncio, "sleep", _noop_sleep)


def test_embed_batches_texts_into_single_request(monkeypatch) -> None:
    client = FakeClient([FakeResponse(payload=[MATRIX_A, MATRIX_B, MATRIX_C])])
    _patch(monkeypatch, client)

    vectors = embeddings.asyncio.run(embeddings.embed(["a", "b", "c"]))

    assert vectors == [[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]]
    assert client.calls == [
        {"inputs": ["a", "b", "c"], "options": {"wait_for_model": True}}
    ]


def test_embed_retries_on_retryable_status_then_succeeds(monkeypatch) -> None:
    client = FakeClient(
        [
            FakeResponse(status_code=503, payload=None),
            FakeResponse(payload=MATRIX_A),
        ]
    )
    _patch(monkeypatch, client)

    vectors = embeddings.asyncio.run(embeddings.embed(["a"]))

    assert vectors == [[0.0, 0.0]]
    assert len(client.calls) == 2


def test_embed_single_text_mean_pools_token_rows(monkeypatch) -> None:
    client = FakeClient([FakeResponse(payload=MATRIX_B)])
    _patch(monkeypatch, client)

    vectors = embeddings.asyncio.run(embeddings.embed(["a"]))

    assert vectors == [[1.0, 1.0]]
    assert client.calls == [{"inputs": "a", "options": {"wait_for_model": True}}]