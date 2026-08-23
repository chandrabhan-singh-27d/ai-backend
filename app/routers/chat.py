from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.llm import chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    model: str

class ToolChatRequest(BaseModel):
    message: str

class ToolChatResponse(BaseModel):
    response: str
    tool_used: bool

@router.post("/chat")
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    try:
        content = await chat(request.message)
        return ChatResponse(response=content, model="qwen/qwen3.6-27b")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

@router.post("/chat/tools")
async def tool_chat_endpoint(request: ToolChatRequest) -> ToolChatResponse:
    try:
        content = await chat(request.message, tools_enabled=True)
        return ToolChatResponse(response=content, tool_used=True)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e