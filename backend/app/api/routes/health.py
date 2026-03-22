from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/settings")
def health_settings() -> dict[str, object]:
    settings = get_settings()
    return {
        "model_provider": settings.model_provider,
        "model_name": settings.model_name,
        "model_base_url": settings.model_base_url,
        "model_api_key_set": bool(settings.model_api_key),
        "model_api_key_length": len(settings.model_api_key or ""),
    }
