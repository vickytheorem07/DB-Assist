from typing import Literal

from pydantic import BaseModel


class LoadDocsResponse(BaseModel):
    status: Literal["success"]
    filename: str | None
    message: str
    pages: int
    chunks: int
    table_names: list[str]
