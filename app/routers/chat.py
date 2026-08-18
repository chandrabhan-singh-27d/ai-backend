from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm import chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    model: str


@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    try:
        content = await chat(request.message)
        return ChatResponse(response=content, model="qwen/qwen3.6-27b")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
