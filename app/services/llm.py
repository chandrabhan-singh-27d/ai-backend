import json
import logging
import os
from collections.abc import AsyncIterator
from time import perf_counter

from openai import AsyncOpenAI, AsyncStream
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.completion_usage import CompletionUsage

from app.services.embeddings import embed
from app.services.metrics import LLM_TOKENS, LLM_TTFT, measure_llm_call
from app.services.tools import calculate
from app.services.vector_store import get_store

logger = logging.getLogger("app.services.llm")

client = AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")


def log_llm_usage(segment: str, tools_enabled: bool, total_tokens: int) -> None:
    logger.info(
        "llm_call",
        extra={
            "extra_fields": {
                "segment": segment,
                "model": "qwen/qwen3.6-27b",
                "tools_enabled": "true" if tools_enabled else "false",
                "tokens": total_tokens,
            }
        },
    )


async def iter_chunks(
    stream: AsyncStream[ChatCompletionChunk],
) -> AsyncIterator[ChatCompletionChunk]:
    async for chunk in stream:
        yield chunk


def _log_llm_call(segment: str, tools_enabled: bool, response: ChatCompletion) -> None:
    tokens = response.usage.total_tokens if response.usage else 0
    log_llm_usage(segment, tools_enabled, tokens)


def _strip_reasoning(content: str) -> str:
    if "</think>" in content:
        return content.split("</think>", 1)[1].lstrip()
    return content


async def chat(message: str, tools_enabled: bool = False, max_tokens: int = 400) -> str:
    if tools_enabled:
        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="tool_round"):
            response = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role": "user", "content": message}],
                tools=TOOLS,
                max_tokens=max_tokens,
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
                max_tokens=max_tokens,
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


async def chat_stream(
    message: str, tools_enabled: bool = False, max_tokens: int = 400
) -> AsyncIterator[dict[str, object]]:
    if tools_enabled:
        tool_calls: dict[int, dict[str, str]] = {}
        tool_round_usage: CompletionUsage | None = None

        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="tool_round"):
            stream = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role": "user", "content": message}],
                tools=TOOLS,
                max_tokens=max_tokens,
                stream=True,
                extra_body={
                    "reasoning_format": "hidden",
                    "reasoning_effort": "none",
                    "stream_options": {"include_usage": True},
                },
            )
            async for chunk in iter_chunks(stream):
                for tc in (chunk.choices[0].delta.tool_calls if chunk.choices else None) or []:
                    entry = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    if tc.function:
                        if tc.function.name:
                            entry["name"] += tc.function.name
                        if tc.function.arguments:
                            entry["arguments"] += tc.function.arguments
                if chunk.usage is not None:
                    tool_round_usage = chunk.usage

        if tool_round_usage is not None:
            LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="true").inc(
                tool_round_usage.total_tokens
            )
            log_llm_usage("tool_round", True, tool_round_usage.total_tokens)

        if not tool_calls:
            yield {"type": "done"}
            return

        first = tool_calls[0]
        tool_name = first["name"]
        tool_args = json.loads(first["arguments"] or "{}")
        result = str(TOOL_MAP[tool_name](**tool_args))
        yield {"type": "tool_call", "name": tool_name}

        messages: list[ChatCompletionMessageParam] = [
            {"role": "user", "content": message},
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": first["id"],
                        "type": "function",
                        "function": {"name": tool_name, "arguments": first["arguments"]},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": first["id"], "content": result},
        ]

        final_usage: CompletionUsage | None = None
        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="final"):
            ttft_start = perf_counter()
            ttft_recorded = False
            final: AsyncStream[ChatCompletionChunk] = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,
                max_tokens=max_tokens,
                stream=True,
                extra_body={
                    "reasoning_format": "hidden",
                    "reasoning_effort": "none",
                    "stream_options": {"include_usage": True},
                },
            )
            async for chunk in iter_chunks(final):
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    if not ttft_recorded:
                        LLM_TTFT.labels(model="qwen/qwen3.6-27b", segment="final").observe(
                            perf_counter() - ttft_start
                        )
                        ttft_recorded = True
                    yield {"type": "token", "content": delta.content}
                if chunk.usage is not None:
                    final_usage = chunk.usage

        if final_usage is not None:
            LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="true").inc(
                final_usage.total_tokens
            )
            log_llm_usage("final", True, final_usage.total_tokens)
    else:
        final_usage: CompletionUsage | None = None
        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=False, segment="final"):
            ttft_start = perf_counter()
            ttft_recorded = False
            stream = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{"role": "user", "content": message}],
                max_tokens=max_tokens,
                stream=True,
                extra_body={
                    "reasoning_format": "hidden",
                    "reasoning_effort": "none",
                    "stream_options": {"include_usage": True},
                },
            )
            async for chunk in iter_chunks(stream):
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    if not ttft_recorded:
                        LLM_TTFT.labels(model="qwen/qwen3.6-27b", segment="final").observe(
                            perf_counter() - ttft_start
                        )
                        ttft_recorded = True
                    yield {"type": "token", "content": delta.content}
                if chunk.usage is not None:
                    final_usage = chunk.usage

        if final_usage is not None:
            LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="false").inc(
                final_usage.total_tokens
            )
            log_llm_usage("final", False, final_usage.total_tokens)

    yield {"type": "done"}


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
