import json
import logging

from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.services.llm import TOOL_MAP, TOOLS, client
from app.services.metrics import LLM_TOKENS, measure_llm_call

logger = logging.getLogger("app.services.agent")


async def run_agent(question: str, max_steps: int = 5) -> str:
    messages: list[dict[str, object]] = [{"role": "user", "content": question}]

    for _step in range(max_steps):
        with measure_llm_call(model="qwen/qwen3.6-27b", tools_enabled=True, segment="agent_round"):
            response = await client.chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=messages,  # type: ignore[arg-type]
                tools=TOOLS,
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

        messages.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": tool_call.function.arguments
                    } 
                }
            ]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": str(result)
        })

    return "Agent reached max steps without a final answer."