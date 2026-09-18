import asyncio
from time import sleep
from typing import TypedDict

import httpx
from fastapi import APIRouter, HTTPException

from app.dependencies import PROTECTED
from app.services.ssrf import InvalidFetchUrl, validate_fetch_url

router = APIRouter()


class FetchResponse(TypedDict):
    url: str
    status: int
    content_length: int


class DemoResponse(TypedDict):
    handler: str
    elapsed: int


@router.get("/fetch", dependencies=PROTECTED)
async def fetch_url(url: str) -> FetchResponse:
    try:
        validate_fetch_url(url)
    except InvalidFetchUrl as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=10.0) as client:
            response = await client.get(url)
        return {
            "url": url,
            "status": response.status_code,
            "content_length": len(response.text),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


# Teaching/demo endpoints. Registered only when DEMO_ENDPOINTS=true (default off);
# /slow-blocked intentionally blocks the event loop to demonstrate why that is bad.
demo_router = APIRouter(prefix="/slow", tags=["demo"])


@demo_router.get("/sync")
def sync_demo() -> DemoResponse:
    sleep(3)
    return {"handler": "sync", "elapsed": 3}


@demo_router.get("/async")
async def async_demo() -> DemoResponse:
    await asyncio.sleep(3)
    return {"handler": "async", "elapsed": 3}


@demo_router.get("/blocked")
async def blocked_demo() -> DemoResponse:
    sleep(3)
    return {"handler": "blocked", "elapsed": 3}