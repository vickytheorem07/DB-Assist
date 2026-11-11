import time
from abc import ABC, abstractmethod

from langchain_huggingface import HuggingFaceEmbeddings

from app.core.logger import setup_logger


class Embedding(ABC):
    @abstractmethod
    def embed_documents(self, docs: list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        pass


class Hugging_face_embedding(Embedding):
    def __init__(self, model_name: str, api_key: str | None = None, req_id: str = "N/A"):
        self.logger = setup_logger(__name__, req_id)
        self.logger.info("Loading embedding model: model=%s", model_name)
        try:
            model_kwargs = {"token": api_key} if api_key else {}
            self.embedding = HuggingFaceEmbeddings(
                model_name=model_name,
                model_kwargs=model_kwargs,
            )
        except Exception:
            self.logger.exception("Embedding model initialization failed: model=%s", model_name)
            raise
        self.logger.info("Embedding model loaded: model=%s", model_name)

    def embed_documents(self, docs: list[str]) -> list[list[float]]:
        started = time.perf_counter()
        self.logger.info("Document embedding started: count=%d", len(docs))
        try:
            vectors = self.embedding.embed_documents(docs)
        except Exception:
            self.logger.exception("Document embedding failed: count=%d", len(docs))
            raise
        self.logger.info("Document embedding completed: count=%d elapsed_ms=%.1f", len(docs), (time.perf_counter() - started) * 1000)
        return vectors

    def embed_query(self, query: str) -> list[float]:
        started = time.perf_counter()
        self.logger.info("Query embedding started")
        try:
            vector = self.embedding.embed_query(query)
        except Exception:
            self.logger.exception("Query embedding failed")
            raise
        self.logger.info("Query embedding completed: elapsed_ms=%.1f", (time.perf_counter() - started) * 1000)
        return vector
