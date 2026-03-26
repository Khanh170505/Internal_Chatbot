from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Enterprise Knowledge Copilot", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    database_url: str = Field(default="sqlite:///./app.db", alias="DATABASE_URL")
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    vectorstore_dir: Path = Field(default=Path("./vectorstore"), alias="VECTORSTORE_DIR")

    max_upload_mb_user: int = Field(default=15, alias="MAX_UPLOAD_MB_USER")
    max_upload_mb_admin: int = Field(default=30, alias="MAX_UPLOAD_MB_ADMIN")
    max_upload_files_user: int = Field(default=3, alias="MAX_UPLOAD_FILES_USER")
    max_upload_files_admin: int = Field(default=10, alias="MAX_UPLOAD_FILES_ADMIN")
    max_pdf_pages_user: int = Field(default=120, alias="MAX_PDF_PAGES_USER")
    max_pdf_pages_admin: int = Field(default=300, alias="MAX_PDF_PAGES_ADMIN")

    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3.5:4b", alias="OLLAMA_MODEL")
    ollama_timeout_sec: int = Field(default=180, alias="OLLAMA_TIMEOUT_SEC")

    api_rate_limit_per_minute: int = Field(default=60, alias="API_RATE_LIMIT_PER_MINUTE")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.vectorstore_dir.mkdir(parents=True, exist_ok=True)
    return settings
