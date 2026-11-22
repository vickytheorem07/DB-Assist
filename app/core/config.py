from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACK_END_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACK_END_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


    APP_ENV: str = "local"
    DATABASE_URL: str = ""
    SECRET_KEY: str = "unsafe-development-secret-change-me"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    limit_history_of_conversation: int = 10
    MAX_DOCUMENT_PAGES: int = 10
    MAX_UPLOAD_SIZE_MB: int = 10
    CHUNK_SIZE_TOKENS: int = 500
    CHUNK_OVERLAP_TOKENS: int = 250
    TIKTOKEN_ENCODING: str = "cl100k_base"

    groq_llm_api_key: str
    llm_model_name: str = "openai/gpt-oss-20b"
    temperature: float = 0.9
    huggingface_embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    huggingface_api: str | None = None
    persist_dir: str = "chroma_db"
    collection_name: str = "documents"
    top_k: int = 3
    LANGSMITH_API_KEY: str

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
    return Settings()  # pyright: ignore[reportCallIssue]


settings = get_settings()
