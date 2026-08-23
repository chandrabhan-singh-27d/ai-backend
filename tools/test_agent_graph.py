import asyncio

from dotenv import load_dotenv

from app.services.agent import run_agent
from app.services.agent_graph import run_agent_graph

load_dotenv()


QUESTION = "Use the calculator tool to compute sqrt(144), then tell me the answer."


async def main() -> None:
    hand_rolled = await run_agent(QUESTION)
    print("hand-rolled agent:")
    print(hand_rolled)
    print()

    graph = await run_agent_graph(QUESTION)
    print("langgraph agent:")
    print(graph)


if __name__ == "__main__":
    asyncio.run(main())
