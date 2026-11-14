from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class InteractAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_query: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000),
    ]
    conversation_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    ]


class InteractAgentResponse(BaseModel):
    agent_response: str
    user_query: str
    req_id: str
