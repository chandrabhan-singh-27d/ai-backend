import json
import os

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionToolParam
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.services.embeddings import embed
from app.services.tools import calculate
from app.services.vector_store import search, store

client = AsyncOpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")


def _strip_reasoning(content: str) -> str:
    if "</think>" in content:
        return content.split("</think>", 1)[1].lstrip()
    return content


async def chat(message: str, tools_enabled: bool = False) -> str:
    if tools_enabled:
        response = await client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": message}],
            tools=TOOLS,
            extra_body={"reasoning_format": "hidden"},
        )
    else:
        response = await client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": message}],
            extra_body={"reasoning_format": "hidden"},
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
            extra_body={"reasoning_format": "hidden"},
        )
        return _strip_reasoning(final.choices[0].message.content or "")
    return _strip_reasoning(choice.message.content or "")


def _search_documents(query: str, top_k: int = 3) -> str:
    query_embedding = embed([query])[0]
    results = search(query_embedding, top_k=top_k)
    if not results:
        return "No results."
    return "\n".join(f"- [{r['id']}] {r['text']} (score: {r['score']:.3f})" for r in results)


def _list_documents() -> str:
    if not store:
        return "No documents stored."
    return "\n".join(f"- [{doc_id}] {doc['text'][:80]}" for doc_id, doc in store.items())


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
