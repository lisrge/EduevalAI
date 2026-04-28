from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_PATH = str((Path(__file__).resolve().parents[2] / ".env"))


class Settings(BaseSettings):
    app_name: str = "EduEval AI Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8001

    database_url: str = "mysql+pymysql://user:password@127.0.0.1:3306/edueval_ai?charset=utf8mb4"

    cors_origins: str = "*"

    storage_root: str = "./storage"
    preview_converter_path: str = "soffice"
    model_provider: str = "openai-compatible"
    model_name: str = "deepseek-chat"
    model_base_url: str | None = None
    model_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
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


def get_settings() -> Settings:
    return Settings()
