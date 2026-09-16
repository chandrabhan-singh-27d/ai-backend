import asyncio

import httpx

from app.config import HF_EMBEDDINGS_URL, HF_TOKEN

_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        headers = {"Authorization": f"Bearer {HF_TOKEN}"} if HF_TOKEN else {}
        _client = httpx.AsyncClient(headers=headers, timeout=60.0)
    return _client


async def embed(texts: list[str]) -> list[list[float]]:
    if not HF_TOKEN:
        raise RuntimeError("HF_TOKEN is not set; add it to .env for Hugging Face embeddings")
    results: list[list[float]] = []
    for text in texts:
        response = await _get_client().post(
            HF_EMBEDDINGS_URL,
            json={"inputs": text, "options": {"wait_for_model": True}},
        )
        response.raise_for_status()
        vector = response.json()
        if vector and isinstance(vector[0], list):
            rows = [[float(x) for x in row] for row in vector]
            dim = len(rows[0])
            vector = [sum(row[i] for row in rows) / len(rows) for i in range(dim)]
        results.append([float(x) for x in vector])
    return results


def embed_sync(texts: list[str]) -> list[list[float]]:
    return asyncio.run(embed(texts))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b)