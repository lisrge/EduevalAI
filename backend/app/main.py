import asyncio
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.applications import router as applications_router
from app.api.routes.assignments import router as assignments_router
from app.api.routes.blogs import router as blogs_router
from app.api.routes.document_drafts import router as drafts_router
from app.api.routes.exports import router as exports_router
from app.api.routes.health import router as health_router
from app.api.routes.repositories import router as repositories_router
from app.api.routes.submissions import router as submissions_router
from app.api.routes.teacher_scores import router as teacher_scores_router
from app.api.routes.users import router as users_router
from app.api.routes.workloads import router as workloads_router
from app.core.config import get_settings
from app.db.init_db import init_db
from app.services.repo_scheduler_service import start_repo_scheduler, stop_repo_scheduler

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

settings = get_settings()
app = FastAPI(title=settings.app_name)

allow_all_origins = settings.cors_origin_list == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else settings.cors_origin_list,
    allow_credentials=False if allow_all_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(blogs_router, prefix="/api")
app.include_router(drafts_router, prefix="/api")
app.include_router(applications_router, prefix="/api")
app.include_router(assignments_router, prefix="/api")
app.include_router(submissions_router, prefix="/api")
app.include_router(teacher_scores_router, prefix="/api")
app.include_router(repositories_router, prefix="/api")
app.include_router(workloads_router, prefix="/api")
app.include_router(exports_router, prefix="/api")


@app.on_event("startup")
def _on_startup() -> None:
    init_db()
    start_repo_scheduler()


@app.on_event("shutdown")
def _on_shutdown() -> None:
    stop_repo_scheduler()


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "status": "running",
    }


@app.get("/api")
@app.get("/api/")
def api_root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "env": settings.app_env,
        "status": "running",
    }
