import time
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any

from langchain_core.documents import Document
from langchain_chroma import Chroma

from app.core.logger import setup_logger


class VectorDB(ABC):
    @abstractmethod
    def add_documents(self, docs: list[Document]) -> list[str]:
        ...

    @abstractmethod
    def similarity_search(self, query: str, k: int = 3) -> list[Document]:
        ...

    @abstractmethod
    def update_document(self, doc_id: str, doc: Document) -> None:
        ...

    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        ...

    @abstractmethod
    def get_all(self) -> dict[str, Any]:
        ...


class ChromaVectorDB(VectorDB):
    _insert_lock = Lock()

    def __init__(self, embedding_model, collection_name: str, persist_dir: str, req_id: str = "N/A"):
        self.logger = setup_logger(__name__, req_id)
        self.collection_name = collection_name
        self.logger.info("Opening Chroma collection: collection=%s persist_dir=%s", collection_name, persist_dir)
        try:
            self.db = Chroma(
                collection_name=collection_name,
                persist_directory=persist_dir,
                embedding_function=embedding_model,
            )
        except Exception:
            self.logger.exception("Could not open Chroma collection: collection=%s", collection_name)
            raise

    def add_documents(self, docs: list[Document]) -> list[str]:
        started = time.perf_counter()
        self.logger.info("Vector collection replacement started: collection=%s new_count=%d", self.collection_name, len(docs))
        try:
            # Replace the collection contents for this upload; IDs restart at 1.
            with self._insert_lock:
                existing_ids = self.db.get(include=[])["ids"]
                if existing_ids:
                    self.logger.info(
                        "Replacing existing vector documents: collection=%s old_count=%d",
                        self.collection_name,
                        len(existing_ids),
                    )
                    self.db.delete(ids=existing_ids)
                self.logger.info(
                    "Vector collection cleared: collection=%s remaining_count=0",
                    self.collection_name,
                )
                if not docs:
                    self.logger.warning(
                        "No new documents supplied after clearing collection: collection=%s",
                        self.collection_name,
                    )
                    return []

                # Each replacement starts IDs at 1.
                ids = [str(index + 1) for index in range(len(docs))]
                inserted_ids = self.db.add_documents(documents=docs, ids=ids)
        except Exception:
            self.logger.exception("Vector collection replacement failed: collection=%s new_count=%d", self.collection_name, len(docs))
            raise
        self.logger.info("Vector collection replacement completed: collection=%s count=%d elapsed_ms=%.1f", self.collection_name, len(inserted_ids), (time.perf_counter() - started) * 1000)
        return inserted_ids

    def similarity_search(self, query: str, k: int = 3) -> list[Document]:
        started = time.perf_counter()
        self.logger.info("Vector search started: collection=%s k=%d", self.collection_name, k)
        try:
            documents = self.db.similarity_search(query, k=k)
        except Exception:
            self.logger.exception("Vector search failed: collection=%s k=%d", self.collection_name, k)
            raise
        self.logger.info("Vector search completed: collection=%s result_count=%d elapsed_ms=%.1f", self.collection_name, len(documents), (time.perf_counter() - started) * 1000)
        return documents

    def update_document(self, doc_id: str, doc: Document) -> None:
        self.logger.info("Vector document update started: collection=%s", self.collection_name)
        try:
            self.db.update_documents(ids=[doc_id], documents=[doc])
        except Exception:
            self.logger.exception("Vector document update failed: collection=%s", self.collection_name)
            raise
        self.logger.info("Vector document update completed: collection=%s", self.collection_name)

    def delete_document(self, doc_id: str) -> None:
        self.logger.info("Vector document deletion started: collection=%s", self.collection_name)
        try:
            self.db.delete(ids=[doc_id])
        except Exception:
            self.logger.exception("Vector document deletion failed: collection=%s", self.collection_name)
            raise
        self.logger.info("Vector document deletion completed: collection=%s", self.collection_name)

    def get_all(self) -> dict[str, Any]:
        try:
            result = self.db.get()
        except Exception:
            self.logger.exception("Could not list Chroma collection: collection=%s", self.collection_name)
            raise
        self.logger.info("Chroma collection inspected: collection=%s document_count=%d", self.collection_name, len(result.get("ids", [])))
        return result
