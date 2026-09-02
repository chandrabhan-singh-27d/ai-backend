import json
import logging
import os
from typing import TypedDict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent, Tool
from openai import AsyncOpenAI
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.services.metrics import LLM_TOKENS, measure_llm_call

logger = logging.getLogger("app.services.agent_mcp")

client = AsyncOpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

MCP_PARAMS = StdioServerParameters(
    command="uv",
    args=["run", "python", "servers/documents.py"],
    env={"PYTHONPATH": ".", "PYTHONUNBUFFERED": "1"},
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


async def run_mcp_agent(question: str, max_steps: int = 5) -> str:
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
                model="qwen/qwen3.6-27b", tools_enabled=True, segment="agent_mcp"
            ):
                response = await client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=messages,  # type: ignore[arg-type]
                    tools=openai_tools,  # type: ignore[arg-type]
                )
            if response.usage is not None:
                LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="true").inc(
                    response.usage.total_tokens
                )

            choice = response.choices[0]

            if not choice.message.tool_calls:
                return choice.message.content or ""

            tool_call = choice.message.tool_calls[0]
            assert isinstance(tool_call, ChatCompletionMessageFunctionToolCall)
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            result = await session.call_tool(tool_name, tool_args)

            content = result.content[0]
            assert isinstance(content, TextContent)
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
