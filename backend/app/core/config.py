import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = str((Path(__file__).resolve().parents[2] / ".env"))


class Settings(BaseSettings):
    app_name: str = "EduEval AI Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    site_basic_auth_username: str | None = None
    site_basic_auth_password: str | None = None

    database_url: str = "sqlite+pysqlite:///./edueval_ai.sqlite3"

    cors_origins: str = "*"

    storage_root: str = "./storage"
    submission_storage_root: str | None = None
    preview_converter_path: str = "soffice"
    model_provider: str = "openai-compatible"
    model_name: str = "deepseek-chat"
    model_base_url: str | None = None
    model_api_key: str | None = None
    upload_session_ttl_hours: int = 24
    upload_chunk_size_mb: int = 5
    upload_max_file_size_gb: int = 4
    repo_auto_sync_enabled: bool = True
    repo_auto_sync_poll_minutes: int = 15
    repo_auto_sync_weekday: int = 1
    repo_auto_sync_hour: int = 3
    repo_auto_sync_max_pages: int = 3
    repo_preload_batch_size: int = 4
    repo_startup_preload_batch_size: int = 200
    repo_analysis_max_age_hours: int = 12
    teacher_score_refresh_enabled: bool = True
    teacher_score_refresh_poll_minutes: int = 120
    teacher_score_refresh_max_age_hours: int = 6
    teacher_score_refresh_batch_size: int = 10
    blog_crawler_enabled: bool = True
    blog_crawler_source: str = "csdn"
    blog_cdp_url: str = "http://127.0.0.1:9222"
    blog_launch_chrome: bool = True
    blog_chrome_exe: str | None = None
    blog_profile_dir: str = "./storage/browser_profile"
    blog_max_pages: int = 100
    blog_max_posts_per_source: int = 500
    blog_min_delay_seconds: float = 2.0
    blog_max_delay_seconds: float = 5.0
    blog_navigation_timeout_ms: int = 45000
    blog_page_load_wait_ms: int = 2000

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def storage_path(self) -> Path:
        return (self.backend_root / self.storage_root).resolve()

    @property
    def application_storage_path(self) -> Path:
        return self.storage_path / "applications"

    @property
    def export_storage_path(self) -> Path:
        return self.storage_path / "exports"

    @property
    def preview_storage_path(self) -> Path:
        return self.storage_path / "previews"

    @property
    def submission_storage_path(self) -> Path:
        if self.submission_storage_root:
            root = Path(self.submission_storage_root)
            if not root.is_absolute():
                root = self.backend_root / root
            return root.resolve()
        return self.storage_path / "submissions"

    @property
    def upload_session_storage_path(self) -> Path:
        return self.storage_path / "upload_sessions"

    @property
    def upload_chunk_size_bytes(self) -> int:
        return max(int(self.upload_chunk_size_mb or 5), 1) * 1024 * 1024

    @property
    def upload_max_file_size_bytes(self) -> int:
        return max(int(self.upload_max_file_size_gb or 4), 1) * 1024 * 1024 * 1024

    @property
    def blog_storage_path(self) -> Path:
        return self.storage_path / "blogs"

    @property
    def blog_screenshot_storage_path(self) -> Path:
        return self.blog_storage_path / "screenshots"

    @property
    def blog_html_storage_path(self) -> Path:
        return self.blog_storage_path / "html"

    @property
    def blog_profile_storage_path(self) -> Path:
        return (self.backend_root / self.blog_profile_dir).resolve()


def get_settings() -> Settings:
    for key in ("MODEL_BASE_URL", "MODEL_API_KEY", "MODEL_NAME", "MODEL_PROVIDER"):
        if os.environ.get(key, None) == "":
            os.environ.pop(key, None)
    return Settings()
