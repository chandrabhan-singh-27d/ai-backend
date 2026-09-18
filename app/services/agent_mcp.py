import json
import logging
import os
import sys
from typing import TypedDict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent, Tool
from openai import AsyncOpenAI
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.config import (
    AGENT_MAX_STEPS,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_REASONING_EFFORT,
    LLM_REASONING_FORMAT,
    LLM_TIMEOUT_SECONDS,
)
from app.services.metrics import LLM_TOKENS, measure_llm_call

logger = logging.getLogger("app.services.agent_mcp")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set; copy .env.example to .env and add your key"
    )

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url=GROQ_BASE_URL,
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=LLM_MAX_RETRIES,
)

MCP_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["servers/documents.py"],
    env={**os.environ, "PYTHONPATH": os.path.abspath("."), "PYTHONUNBUFFERED": "1"},
)


class MCPTools(TypedDict):
    type: str
    function: object


def mcp_tools_to_openai(mcp_tools: list[Tool]) -> list[MCPTools]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.input_schema,
            },
        }
        for tool in mcp_tools
    ]


async def run_mcp_agent(
    question: str, max_steps: int = AGENT_MAX_STEPS, max_tokens: int = LLM_MAX_TOKENS
) -> str:
    async with (
        stdio_client(MCP_PARAMS) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()

        mcp_tools = await session.list_tools()
        openai_tools = mcp_tools_to_openai(mcp_tools.tools)

        messages: list[dict[str, object]] = [{"role": "user", "content": question}]

        for _step in range(max_steps):
            with measure_llm_call(
                model=LLM_MODEL, tools_enabled=True, segment="agent_mcp"
            ):
                response = await client.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,  # type: ignore[arg-type]
                    tools=openai_tools,  # type: ignore[arg-type]
                    max_tokens=max_tokens,
                    extra_body={
                        "reasoning_format": LLM_REASONING_FORMAT,
                        "reasoning_effort": LLM_REASONING_EFFORT,
                    },
                )
            if response.usage is not None:
                LLM_TOKENS.labels(model=LLM_MODEL, tools_enabled="true").inc(
                    response.usage.total_tokens
                )

            choice = response.choices[0]

            if not choice.message.tool_calls:
                return choice.message.content or ""

            tool_call = choice.message.tool_calls[0]
            if not isinstance(tool_call, ChatCompletionMessageFunctionToolCall):
                raise ValueError(f"unsupported tool call type: {type(tool_call).__name__}")
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            result = await session.call_tool(tool_name, tool_args)

            content = result.content[0]
            if not isinstance(content, TextContent):
                raise ValueError(f"unsupported MCP tool result type: {type(content).__name__}")
            tool_result = content.text

            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": tool_call.function.arguments,
                            },
                        }
                    ],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

        return "Agent reached max steps without a final answer."
