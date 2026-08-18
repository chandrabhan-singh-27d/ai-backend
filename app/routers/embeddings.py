from fastapi import APIRouter
from pydantic import BaseModel

from app.services.embeddings import cosine_similarity, embed

router = APIRouter()


class EmbedRequst(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


class SimilarityRequest(BaseModel):
    text_a: str
    text_b: str


class SimilarityResponse(BaseModel):
    text_a: str
    text_b: str
    similarity: float


@router.post("/embeddings", response_model=EmbedResponse)
def create_embeddings(request: EmbedRequst) -> EmbedResponse:
    return EmbedResponse(embeddings=embed(request.texts))


@router.post("/similarity", response_model=SimilarityResponse)
def check_similarity(request: SimilarityRequest) -> SimilarityResponse:
    vec_a = embed([request.text_a])[0]
    vec_b = embed([request.text_b])[0]
    score = cosine_similarity(vec_a, vec_b)

    return SimilarityResponse(
        text_a=request.text_a, text_b=request.text_b, similarity=round(score, 4)
    )
