from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class ConversationHistoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]
    limit: int = Field(default=10, ge=1, le=100)


class ConversationHistoryMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: int
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    count: int
    messages: list[ConversationHistoryMessage]
