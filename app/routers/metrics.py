from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()

@router.get("/metrics", response_class=PlainTextResponse)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
