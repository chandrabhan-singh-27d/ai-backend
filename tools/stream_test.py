import asyncio
import json

import httpx

from app.main import app


async def _dump(client: httpx.AsyncClient, path: str, body: dict[str, object]) -> None:
    print(f"\n=== POST {path} {body}")
    async with client.stream("POST", path, json=body) as response:
        print("status:", response.status_code, response.headers.get("content-type"))
        async for line in response.aiter_lines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("data: "):
                print("  event:", json.loads(stripped[len("data: ") :]))
            else:
                print("  body:", stripped)


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await _dump(
            client,
            "/chat",
            {"message": "What is the capital of France? One sentence.", "stream": True},
        )
        await _dump(
            client,
            "/chat/tools",
            {"message": "What is 6 * 7? One sentence.", "stream": True},
        )
        await _dump(
            client,
            "/agent",
            {"question": "What is 123 + 456? One sentence.", "stream": True},
        )


if __name__ == "__main__":
    asyncio.run(main())
