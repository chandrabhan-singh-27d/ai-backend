import asyncio
import time
from typing import TypedDict

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()


class Response(TypedDict):
    handler: str
    elapsed: int

class FetchResponse(TypedDict):
    url: str
    status: int
    content_length: int


@router.get("/slow-sync")
def sync_demo() -> Response:
    time.sleep(3)
    return {"handler": "sync", "elapsed": 3}


@router.get("/slow-async")
async def async_demo() -> Response:
    await asyncio.sleep(3)
    return {"handler": "async", "elapsed": 3}

@router.get("/slow-blocked")
async def blocked_demo() -> Response:
    time.sleep(3)
    return {
        "handler": "blocked",
        "elapsed": 3
    }

@router.get("/fetch")
async def fetch_url(url: str) -> FetchResponse:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
        return {
            "url": url,
            "status": response.status_code,
            "content_length": len(response.text)
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e