import json
import logging
import os

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionToolParam
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.services.embeddings import embed
from app.services.metrics import LLM_TOKENS, measure_llm_call
from app.services.tools import calculate
from app.services.vector_store import get_store

logger = logging.getLogger("app.services.llm")

client = AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")


def _log_llm_call(segment: str, tools_enabled: bool, response: ChatCompletion) -> None:
    tokens = response.usage.total_tokens if response.usage else 0
    logger.info(
        "llm_call",
        extra={
            "extra_fields": {
                "segment": segment,
                "model": "qwen/qwen3.6-27b",
                "tools_enabled": "true" if tools_enabled else "false",
                "tokens": tokens,
            }
        },
    )


def _strip_reasoning(content: str) -> str:
    if "</think>" in content:
        return content.split("</think>", 1)[1].lstrip()
    return content


async def chat(message: str, tools_enabled: bool = False) -> str:
    if tools_enabled:
        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="tool_round"):
            response = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role": "user", "content": message}],
                tools=TOOLS,
                max_tokens=400,
                extra_body={"reasoning_format": "hidden", "reasoning_effort": "none"},
            )
        if response.usage is not None:
            LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="true").inc(
                response.usage.total_tokens
            )
        _log_llm_call("tool_round", True, response)
    else:
        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=False, segment="final"):
            response = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role": "user", "content": message}],
                max_tokens=400,
                extra_body={"reasoning_format": "hidden", "reasoning_effort": "none"},
            )
        if response.usage is not None:
            LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="false").inc(
                response.usage.total_tokens
            )
        _log_llm_call("final", False, response)

    choice = response.choices[0]

    if choice.message.tool_calls:
        tool_call = choice.message.tool_calls[0]
        assert isinstance(tool_call, ChatCompletionMessageFunctionToolCall)
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        result = TOOL_MAP[tool_name](**tool_args)

        messages = [
            {"role": "user", "content": message},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tool_call.function.arguments},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": tool_call.id, "content": str(result)},
        ]

        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="final"):
            final = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,  # type: ignore[arg-type]
                max_tokens=400,
                extra_body={"reasoning_format": "hidden", "reasoning_effort": "none"},
            )
        if final.usage is not None:
            LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="true").inc(
                final.usage.total_tokens
            )
        _log_llm_call("final", True, final)
        return _strip_reasoning(final.choices[0].message.content or "")
    return _strip_reasoning(choice.message.content or "")


def _search_documents(query: str, top_k: int = 3) -> str:
    query_embedding = embed([query])[0]
    results = get_store().search(query_embedding, top_k=top_k)
    if not results:
        return "No results."
    return "\n".join(f"- [{r['id']}] {r['text']} (score: {r['score']:.3f})" for r in results)


def _list_documents() -> str:
    docs = get_store().list_all()
    if not docs:
        return "No documents stored."
    return "\n".join(f"- [{doc['id']}] {doc['text'][:80]}" for doc in docs)


TOOLS: list[ChatCompletionToolParam] = [
    ChatCompletionToolParam(
        type="function",
        function={
            "name": "calculate",
            "description": "Evaluate a mathematical expression",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expressions like '2+2' or 'sqrt(16)'",
                    }
                },
                "required": ["expression"],
            },
        },
    ),
    ChatCompletionToolParam(
        type="function",
        function={
            "name": "search_documents",
            "description": "Search documents by semantic similarity",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "integer", "description": "Number of results"},
                },
                "required": ["query"],
            },
        },
    ),
    ChatCompletionToolParam(
        type="function",
        function={
            "name": "list_documents",
            "description": "List all stored documents",
            "parameters": {"type": "object", "properties": {}},
        },
    ),
]

TOOL_MAP = {
    "calculate": calculate,
    "search_documents": _search_documents,
    "list_documents": _list_documents,
}
