from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import PROTECTED
from app.services.rag import answer_question

router = APIRouter(dependencies=PROTECTED)


class RAGRequest(BaseModel):
    question: str


class RAGResponse(BaseModel):
    answer: str


@router.post("/rag")
async def ask_question(request: RAGRequest) -> RAGResponse:
    answer = await answer_question(question=request.question)
    return RAGResponse(answer=answer)
