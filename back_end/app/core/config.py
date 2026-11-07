from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "local"
    DATABASE_URL: str = "postgresql+psycopg://taskapp:replace-me@localhost:5432/taskdb"
    SECRET_KEY: str = "unsafe-development-secret-change-me"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    MAX_DOCUMENT_PAGES: int = 10
    MAX_UPLOAD_SIZE_MB: int = 10
    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 250
    TIKTOKEN_ENCODING: str = "cl100k_base"

    @field_validator("MAX_DOCUMENT_PAGES", "MAX_UPLOAD_SIZE_MB", "CHUNK_SIZE_TOKENS")
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Configured limits must be greater than zero")
        return value

    @field_validator("CHUNK_OVERLAP_TOKENS")
    @classmethod
    def validate_nonnegative_overlap(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Chunk overlap cannot be negative")
        return value

    @model_validator(mode="after")
    def validate_chunk_settings(self):
        if self.CHUNK_OVERLAP_TOKENS >= self.CHUNK_SIZE_TOKENS:
            raise ValueError("CHUNK_OVERLAP_TOKENS must be smaller than CHUNK_SIZE_TOKENS")
        if not self.TIKTOKEN_ENCODING.strip():
            raise ValueError("TIKTOKEN_ENCODING cannot be empty")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
