from sentence_transformers import SentenceTransformer

from app.config import EMBEDDING_MODEL

_model = SentenceTransformer(EMBEDDING_MODEL)  # pyright: ignore[reportUnknownMemberType]


def embed(texts: list[str]) -> list[list[float]]:
    embeddings = _model.encode(texts, convert_to_numpy=True)  # pyright: ignore[reportUnknownMemberType,reportUnknownMemberAccess]
    return embeddings.tolist()  # pyright: ignore[reportUnknownMemberType]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    return dot / (norm_a * norm_b)
