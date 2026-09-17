# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
import json
import logging
import operator
from typing import Annotated, TypedDict, cast

from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)

from app.config import AGENT_GRAPH_RECURSION_LIMIT, LLM_MAX_TOKENS, LLM_MODEL
from app.services.llm import TOOLS, call_tool, client
from app.services.metrics import LLM_TOKENS, measure_llm_call

logger = logging.getLogger("app.services.agent_graph")


class AgentState(TypedDict):
    messages: Annotated[list[dict[str, object]], operator.add]


def _build_graph(max_tokens: int = LLM_MAX_TOKENS):
    async def call_llm(state: AgentState) -> dict[str, list[dict[str, object]]]:
        with measure_llm_call(model=LLM_MODEL, tools_enabled=True, segment="agent_graph"):
            response = await client.chat.completions.create(
                model=LLM_MODEL,
                messages=state["messages"],  # type: ignore[arg-type]
                tools=TOOLS,
                max_tokens=max_tokens,
            )
        if response.usage is not None:
            LLM_TOKENS.labels(model=LLM_MODEL, tools_enabled="true").inc(
                response.usage.total_tokens
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

    builder = StateGraph(AgentState)
    builder.add_node("call_llm", call_llm)
    builder.add_node("run_tools", run_tools)

    builder.add_edge(START, "call_llm")
    builder.add_conditional_edges("call_llm", route_after_llm)
    builder.add_edge("run_tools", "call_llm")

    return builder.compile()


async def run_tools(state: AgentState) -> dict[str, list[dict[str, object]]]:
    last_message = state["messages"][-1]
    raw_tool_calls = cast("list[object]", last_message["tool_calls"])
    tool_call = cast("dict[str, object]", raw_tool_calls[0])
    function = cast("dict[str, object]", tool_call["function"])

    tool_name = cast("str", function["name"])
    arguments = cast("str", function["arguments"])
    tool_call_id = cast("str", tool_call["id"])

    tool_args = json.loads(arguments)
    result = await call_tool(tool_name, **tool_args)

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


async def run_agent_graph(question: str, max_tokens: int = LLM_MAX_TOKENS) -> str:
    graph = _build_graph(max_tokens)
    try:
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": AGENT_GRAPH_RECURSION_LIMIT},
        )
    except GraphRecursionError:
        return "Agent reached the graph recursion limit without a final answer."
    messages = cast("list[dict[str, object]]", result["messages"])
    content = messages[-1].get("content")
    assert isinstance(content, str)
    return content
