import json
import os

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.services.tools import calculate

client = AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")

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
    )
]

TOOL_MAP = {"calculate": calculate}


async def chat(message: str, tools_enabled: bool = False) -> str:
    if tools_enabled:
        response = await client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": message}],
            tools=TOOLS,
        )
    else:
        response = await client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": message}],
        )

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

        final = await client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=messages,  # type: ignore[arg-type]
        )
        return final.choices[0].message.content or ""
    return choice.message.content or ""
