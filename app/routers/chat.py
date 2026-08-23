from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.agent import run_agent
from app.services.agent_mcp import run_mcp_agent
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


class AgentRequest(BaseModel):
    question: str


class AgentResponse(BaseModel):
    answer: str


class MCPAgentRequest(BaseModel):
    question: str


class MCPAgentResponse(BaseModel):
    answer: str


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


@router.post("/agent", response_model=AgentResponse)
async def agent_endpoint(request: AgentRequest) -> AgentResponse:
    answer = await run_agent(request.question)
    return AgentResponse(answer=answer)


@router.post("/agent/mcp", response_model=MCPAgentResponse)
async def mcp_agent_endpoint(request: MCPAgentRequest) -> MCPAgentResponse:
    answer = await run_mcp_agent(request.question)
    return MCPAgentResponse(answer=answer)
