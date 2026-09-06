import json
import logging
from collections.abc import AsyncIterator
from time import perf_counter

from openai import AsyncStream
from openai.types.chat import ChatCompletionChunk, ChatCompletionMessageParam
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.completion_usage import CompletionUsage

from app.services.llm import TOOL_MAP, TOOLS, client, iter_chunks, log_llm_usage
from app.services.metrics import LLM_TOKENS, LLM_TTFT, measure_llm_call

logger = logging.getLogger("app.services.agent")


async def run_agent(question: str, max_steps: int = 5, max_tokens: int = 400) -> str:
    messages: list[dict[str, object]] = [{"role": "user", "content": question}]

    for _step in range(max_steps):
        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="agent_round"):
            response = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,  # type: ignore[arg-type]
                tools=TOOLS,
                max_tokens=max_tokens,
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
        result = TOOL_MAP[tool_name](**tool_args)

        messages.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tool_call.function.arguments},
                    }
                ],
            }
        )
        messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": str(result)})

    return "Agent reached max steps without a final answer."


async def run_agent_stream(
    question: str, max_steps: int = 5, max_tokens: int = 400
) -> AsyncIterator[dict[str, object]]:
    messages: list[ChatCompletionMessageParam] = [{"role": "user", "content": question}]

    for _step in range(max_steps):
        tool_calls: dict[int, dict[str, str]] = {}
        usage: CompletionUsage | None = None

        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="agent_round"):
            ttft_start = perf_counter()
            ttft_recorded = False
            stream: AsyncStream[ChatCompletionChunk] = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,
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
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta:
                    if delta.content:
                        if not ttft_recorded:
                            LLM_TTFT.labels(model="qwen/qwen3.6-27b", segment="agent").observe(
                                perf_counter() - ttft_start
                            )
                            ttft_recorded = True
                        yield {"type": "token", "content": delta.content}
                    for tc in delta.tool_calls or []:
                        entry = tool_calls.setdefault(
                            tc.index, {"id": "", "name": "", "arguments": ""}
                        )
                        if tc.function:
                            if tc.function.name:
                                entry["name"] += tc.function.name
                            if tc.function.arguments:
                                entry["arguments"] += tc.function.arguments
                if chunk.usage is not None:
                    usage = chunk.usage

        if usage is not None:
            LLM_TOKENS.labels(model="qwen/qwen3.6-27b", tools_enabled="true").inc(
                usage.total_tokens
            )
            log_llm_usage("agent_round", True, usage.total_tokens)

        if not tool_calls:
            break

        first = tool_calls[0]
        tool_name = first["name"]
        tool_args = json.loads(first["arguments"] or "{}")
        result = TOOL_MAP[tool_name](**tool_args)
        yield {"type": "tool_call", "name": tool_name}

        messages.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": first["id"],
                        "type": "function",
                        "function": {"name": tool_name, "arguments": first["arguments"]},
                    }
                ],
            }
        )
        messages.append({"role": "tool", "tool_call_id": first["id"], "content": str(result)})
    else:
        yield {"type": "token", "content": "Agent reached max steps without a final answer."}

    yield {"type": "done"}
