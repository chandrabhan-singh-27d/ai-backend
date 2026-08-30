from dotenv import load_dotenv
from fastapi import FastAPI

from app.middlewares.request_context import request_context_middleware
from app.routers import chat, demo, documents, embeddings, health, models, rag

load_dotenv()
app = FastAPI(title="AI Backend")
app.middleware("http")(request_context_middleware)
app.include_router(health.router)
app.include_router(models.router)
app.include_router(demo.router)
app.include_router(chat.router)
app.include_router(embeddings.router)
app.include_router(documents.router)
app.include_router(rag.router)
