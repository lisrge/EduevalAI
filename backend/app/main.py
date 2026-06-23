import asyncio
import sys

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.applications import router as applications_router
from app.api.routes.assignments import router as assignments_router
from app.api.routes.blogs import router as blogs_router
from app.api.routes.document_drafts import router as drafts_router
from app.api.routes.document_imports import router as document_imports_router
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
from app.services.blog_crawl_job_service import start_blog_crawl_worker, stop_blog_crawl_worker

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

settings = get_settings()
app = FastAPI(title=settings.app_name)
frontend_dist = (settings.backend_root.parent / "fronted" / "dist").resolve()

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
app.include_router(document_imports_router, prefix="/api")
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
    if settings.blog_crawler_enabled:
        start_blog_crawl_worker()
    if settings.repo_auto_sync_enabled:
        start_repo_scheduler()


@app.on_event("shutdown")
def _on_shutdown() -> None:
    if settings.repo_auto_sync_enabled:
        stop_repo_scheduler()
    if settings.blog_crawler_enabled:
        stop_blog_crawl_worker()


if frontend_dist.exists():
    assets_dir = frontend_dist
    app.mount("/css", StaticFiles(directory=str(assets_dir / "css")), name="frontend-css")
    app.mount("/js", StaticFiles(directory=str(assets_dir / "js")), name="frontend-js")
    app.mount("/img", StaticFiles(directory=str(assets_dir / "img")), name="frontend-img")
    app.mount("/fonts", StaticFiles(directory=str(assets_dir / "fonts")), name="frontend-fonts")

    @app.get("/")
    def root() -> FileResponse:
        return FileResponse(str(frontend_dist / "index.html"))

    @app.get("/favicon.png")
    def favicon() -> FileResponse:
        return FileResponse(str(frontend_dist / "favicon.png"))

    @app.get("/{full_path:path}")
    def frontend_spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            return {
                "name": settings.app_name,
                "env": settings.app_env,
                "status": "running",
            }
        target = frontend_dist / full_path
        if target.is_file():
            return FileResponse(str(target))
        return FileResponse(str(frontend_dist / "index.html"))
else:
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
