import asyncio
import time
from typing import TypedDict

from fastapi import APIRouter

router = APIRouter()


class Response(TypedDict):
    handler: str
    elapsed: int


@router.get("/slow-sync")
def sync_demo() -> Response:
    time.sleep(3)
    return {"handler": "sync", "elapsed": 3}


@router.get("/slow-async")
async def async_demo() -> Response:
    await asyncio.sleep(3)
    return {"handler": "async", "elapsed": 3}
