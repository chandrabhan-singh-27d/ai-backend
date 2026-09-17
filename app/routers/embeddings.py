from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import PROTECTED
from app.services.embeddings import cosine_similarity, embed

router = APIRouter(dependencies=PROTECTED)


class EmbedRequest(BaseModel):
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
async def create_embeddings(request: EmbedRequest) -> EmbedResponse:
    return EmbedResponse(embeddings=await embed(request.texts))


@router.post("/similarity", response_model=SimilarityResponse)
async def check_similarity(request: SimilarityRequest) -> SimilarityResponse:
    vec_a = (await embed([request.text_a]))[0]
    vec_b = (await embed([request.text_b]))[0]
    score = cosine_similarity(vec_a, vec_b)

    return SimilarityResponse(
        text_a=request.text_a, text_b=request.text_b, similarity=round(score, 4)
    )
