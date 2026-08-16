from typing import TypedDict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class Model(TypedDict):
    id: str
    provider: str
    name: str


class ModelCreate(BaseModel):
    id: str
    provider: str
    name: str


MODELS: list[Model] = [
    {"id": "gpt-4o", "provider": "openai", "name": "GPT-4o"},
    {"id": "claude-3-5-sonnet", "provider": "anthropic", "name": "Claude 3.5 Sonnet"},
]


@router.get("/models")
def list_models(provider: str | None = None) -> list[Model]:
    return [m for m in MODELS if provider is None or m["provider"] == provider]


@router.get("/models/{model_id}")
def get_model(model_id: str) -> Model:
    for m in MODELS:
        if m["id"] == model_id:
            return m
    else:
        raise HTTPException(status_code=404, detail="Model not found")


@router.post("/models", status_code=201)
def create_model(payload: ModelCreate) -> Model:
    new_model: Model = {"id": payload.id, "provider": payload.provider, "name": payload.name}
    MODELS.append(new_model)
    return new_model
