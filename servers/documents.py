import anyio
from mcp import types
from mcp.server import Server, ServerRequestContext
from mcp.server.stdio import stdio_server

from app.services.vector_store import get_store

TOOLS = [
    types.Tool(
        name="search_documents",
        description="Search documents by semantic similarity",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {
                    "type": "integer",
                    "description": "Number of results",
                },
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="get_document",
        description="Get a document by its ID",
        input_schema={
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Document ID"},
            },
            "required": ["doc_id"],
        },
    ),
    types.Tool(
        name="list_documents",
        description="List all stored documents",
        input_schema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="add_document",
        description="Add a new document to the store",
        input_schema={
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Document ID"},
                "text": {"type": "string", "description": "Document text"},
            },
            "required": ["doc_id", "text"],
        },
    ),
    types.Tool(
        name="delete_document",
        description="Delete a document by its ID",
        input_schema={
            "type": "object",
            "properties": {
                "doc_id": {"type": "string", "description": "Document ID"},
            },
            "required": ["doc_id"],
        },
    ),
]


def _text(text: str, is_error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        is_error=is_error,
    )


async def handle_list_tools(
    ctx: ServerRequestContext,
    params: types.PaginatedRequestParams | None,
) -> types.ListToolsResult:
    return types.ListToolsResult(tools=TOOLS)


async def handle_call_tool(
    ctx: ServerRequestContext,
    params: types.CallToolRequestParams,
) -> types.CallToolResult:
    args = params.arguments or {}
    name = params.name

    if name == "search_documents":
        from app.services.embeddings import embed

        query_embedding = embed([args["query"]])[0]
        top_k = args.get("top_k", 3)
        results = get_store().search(query_embedding, top_k=top_k)
        if not results:
            return _text("No results.")
        lines = [
            f"- [{r['id']}] {r['text']} (score: {r['score']:.3f})"
            for r in results
        ]
        return _text("\n".join(lines))

    if name == "get_document":
        text = get_store().get(args["doc_id"])
        if text is None:
            return _text(f"Document '{args['doc_id']}' not found.")
        return _text(f"[{args['doc_id']}] {text}")

    if name == "list_documents":
        docs = get_store().list_all()
        if not docs:
            return _text("No documents stored.")
        lines = [
            f"- [{doc['id']}] {doc['text'][:80]}"
            for doc in docs
        ]
        return _text("\n".join(lines))

    if name == "add_document":
        from app.services.embeddings import embed

        embedding = embed([args["text"]])[0]
        get_store().add(doc_id=args["doc_id"], text=args["text"], embedding=embedding)
        return _text(f"Document '{args['doc_id']}' added.")

    if name == "delete_document":
        if not get_store().exists(args["doc_id"]):
            return _text(
                f"Document '{args['doc_id']}' not found.",
                is_error=True,
            )
        get_store().delete(args["doc_id"])
        return _text(f"Document '{args['doc_id']}' deleted.")

    return _text("Unknown tool.", is_error=True)


async def main() -> None:
    server = Server(
        "documents",
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    anyio.run(main)
