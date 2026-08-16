from fastapi import FastAPI

from app.routers import demo, health, models

app = FastAPI(title="AI Backend")
app.include_router(health.router)
app.include_router(models.router)
app.include_router(demo.router)
