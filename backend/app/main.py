from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, careers, health, occupations, rankings
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", docs_url="/api/docs", redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(health.router)
app.include_router(occupations.router, prefix=settings.api_v1_prefix)
app.include_router(rankings.router, prefix=settings.api_v1_prefix)
app.include_router(careers.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "JobsVsAI API", "docs": "/api/docs"}
