from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.model_registry import get_model_store

router = APIRouter()


class ModelCreate(BaseModel):
    id: str
    provider: str
    name: str


@router.get("/models")
def list_models(provider: str | None = None) -> list[dict[str, str]]:
    return get_model_store().list(provider)


@router.get("/models/{model_id}")
def get_model(model_id: str) -> dict[str, str]:
    model = get_model_store().get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/models", status_code=201)
def create_model(payload: ModelCreate) -> dict[str, str]:
    return get_model_store().create(payload.id, payload.provider, payload.name)