import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent


class MCPTestClient:
    """Reusable MCP client for testing servers."""

    def __init__(
        self, command: str, args: list[str], env: dict[str, str] | None = None
    ) -> None:
        self.params = StdioServerParameters(command=command, args=args, env=env)

    async def run(self) -> None:
        async with stdio_client(self.params, errlog=None) as (
            read,
            write,
        ), ClientSession(read, write) as session:
            await session.initialize()
            await self.test(session)

    async def test(self, session: ClientSession) -> None:
        raise NotImplementedError


class DocumentsTest(MCPTestClient):
    """Test the documents MCP server."""

    @staticmethod
    def _text(result: CallToolResult) -> str:
        content = result.content[0]
        assert isinstance(content, TextContent)
        return content.text

    async def test(self, session: ClientSession) -> None:
        tools = await session.list_tools()
        print("=== Available Tools ===")
        for tool in tools.tools:
            print(f"  - {tool.name}: {tool.description}")
        print()

        print("=== Adding Documents ===")
        docs = [
            ("doc1", "Python is a versatile programming language for AI"),
            ("doc2", "PostgreSQL is a powerful open-source relational database"),
            ("doc3", "FastAPI is a modern Python framework for building APIs"),
        ]
        for doc_id, text in docs:
            result = await session.call_tool(
                "add_document", {"doc_id": doc_id, "text": text}
            )
            print(f"  Added '{doc_id}': {self._text(result)}")
        print()

        print("=== Searching ===")
        result = await session.call_tool(
            "search_documents", {"query": "web framework", "top_k": 2}
        )
        print(f"  Results:\n{self._text(result)}")
        print()

        print("=== List All ===")
        result = await session.call_tool("list_documents", {})
        print(f"  {self._text(result)}")
        print()

        print("=== Delete ===")
        result = await session.call_tool("delete_document", {"doc_id": "doc2"})
        print(f"  {self._text(result)}")


if __name__ == "__main__":
    server = sys.argv[1] if len(sys.argv) > 1 else "documents"

    if server == "documents":
        client = DocumentsTest(
            command="uv",
            args=["run", "python", "servers/documents.py"],
            env={"PYTHONPATH": ".", "PYTHONUNBUFFERED": "1"},
        )
        anyio.run(client.run)
    else:
        print(f"Unknown server: {server}")
