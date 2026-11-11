import time
from abc import ABC, abstractmethod

from langchain_groq import ChatGroq

from app.core.logger import setup_logger

logger = setup_logger(__name__)


class llm(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        ...


class Groq_llm(llm):
    def __init__(self, model_name: str, temperature: float, api_key: str):
        self.model_name = model_name
        self.llm = ChatGroq(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
        )
        logger.info("LLM client initialized: model=%s", model_name)

    def generate_response(self, prompt: str) -> str:
        started = time.perf_counter()
        logger.info("LLM request started: model=%s", self.model_name)
        try:
            response = self.llm.invoke(prompt)
        except Exception:
            logger.exception("LLM request failed: model=%s", self.model_name)
            raise
        content = response.content
        logger.info(
            "LLM request completed: model=%s elapsed_ms=%.1f",
            self.model_name,
            (time.perf_counter() - started) * 1000,
        )
        return content
