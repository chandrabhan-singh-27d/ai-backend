from dotenv import load_dotenv
from fastapi import FastAPI

from app.routers import chat, demo, health, models

load_dotenv()
app = FastAPI(title="AI Backend")
app.include_router(health.router)
app.include_router(models.router)
app.include_router(demo.router)
app.include_router(chat.router)
