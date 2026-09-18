import asyncio

import httpx

from app.config import EMBEDDING_TIMEOUT_SECONDS, HF_EMBEDDINGS_URL, HF_TOKEN

_client: httpx.AsyncClient | None = None
_MAX_ATTEMPTS = 3
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
        _client = httpx.AsyncClient(headers=headers, timeout=EMBEDDING_TIMEOUT_SECONDS)
    return _client


def _mean_pool(rows: list[list[float]]) -> list[float]:
    dim = len(rows[0])
    return [sum(row[i] for row in rows) / len(rows) for i in range(dim)]


async def _post_with_retry(payload: dict[str, object]) -> httpx.Response:
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = await _get_client().post(HF_EMBEDDINGS_URL, json=payload)
            if response.status_code in _RETRYABLE_STATUS:
                response.raise_for_status()
            response.raise_for_status()
            return response
        except (httpx.HTTPStatusError, httpx.TransportError):
            if attempt == _MAX_ATTEMPTS - 1:
                raise
            await asyncio.sleep(0.5 * (2**attempt))
    raise RuntimeError("embedding request failed")  # pragma: no cover


async def embed(texts: list[str]) -> list[list[float]]:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is not set; add it to .env for Hugging Face embeddings")
    if not texts:
        return []

    if len(texts) == 1:
        response = await _post_with_retry(
            {"inputs": texts[0], "options": {"wait_for_model": True}}
        )
        vector = response.json()
        if vector and isinstance(vector[0], list):
            rows = [[float(x) for x in row] for row in vector]
            return [_mean_pool(rows)]
        return [[float(x) for x in vector]]

    response = await _post_with_retry(
        {"inputs": texts, "options": {"wait_for_model": True}}
    )
    results: list[list[float]] = []
    for vector in response.json():
        if vector and isinstance(vector[0], list):
            rows = [[float(x) for x in row] for row in vector]
            results.append(_mean_pool(rows))
        else:
            results.append([float(x) for x in vector])
    return results


def embed_sync(texts: list[str]) -> list[list[float]]:
    return asyncio.run(embed(texts))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b)