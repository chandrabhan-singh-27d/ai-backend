# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
import json
import operator
from typing import Annotated, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.services.llm import TOOL_MAP, TOOLS, client


class AgentState(TypedDict):
    messages: Annotated[list[dict[str, object]], operator.add]


async def call_llm(state: AgentState) -> dict[str, list[dict[str, object]]]:
    response = await client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=state["messages"],  # type: ignore[arg-type]
        tools=TOOLS,
    )

    choice = response.choices[0]
    message = choice.message

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        assert isinstance(tool_call, ChatCompletionMessageFunctionToolCall)
        assistant_msg: dict[str, object] = {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            ],
        }
    else:
        assistant_msg = {"role": "assistant", "content": message.content or ""}

    return {"messages": [assistant_msg]}


async def run_tools(state: AgentState) -> dict[str, list[dict[str, object]]]:
    last_message = state["messages"][-1]
    raw_tool_calls = cast("list[object]", last_message["tool_calls"])
    tool_call = cast("dict[str, object]", raw_tool_calls[0])
    function = cast("dict[str, object]", tool_call["function"])

    tool_name = cast("str", function["name"])
    arguments = cast("str", function["arguments"])
    tool_call_id = cast("str", tool_call["id"])

    tool_args = json.loads(arguments)
    result = TOOL_MAP[tool_name](**tool_args)

    tool_msg: dict[str, object] = {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": str(result),
    }

    return {"messages": [tool_msg]}


def route_after_llm(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if "tool_calls" in last_message:
        return "run_tools"
    return END


builder = StateGraph(AgentState)
builder.add_node("call_llm", call_llm)
builder.add_node("run_tools", run_tools)

builder.add_edge(START, "call_llm")
builder.add_conditional_edges("call_llm", route_after_llm)
builder.add_edge("run_tools", "call_llm")

graph = builder.compile()


async def run_agent_graph(question: str) -> str:
    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": question}]}, config={"recursion_limit": 10}
    )
    messages = cast("list[dict[str, object]]", result["messages"])
    content = messages[-1].get("content")
    assert isinstance(content, str)
    return content
