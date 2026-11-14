from pathlib import Path
from io import BytesIO
from datetime import datetime
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, File, Path as PathParam, Query, UploadFile, status

from app.services.db_assist_agent import interact_agent as run_agent
from app.services.load_docs import load_docs as process_document
from app.schemas.load_docs import LoadDocsResponse
from app.schemas.interact_agent import InteractAgentRequest, InteractAgentResponse
from app.schemas.conversation_history import (
    ConversationHistoryRequest,
    ConversationHistoryResponse,
)
from app.dependencies.agent import DbSession
from app.services.conversation_history import fetch_conversation_history

router = APIRouter()



@router.post(
    "/load_doc",
    status_code=status.HTTP_201_CREATED,
    response_model=LoadDocsResponse,
)
async def upload_document(file: UploadFile = File(...)) -> LoadDocsResponse:
    req_id = datetime.now().strftime("%H%M%d%m%y-load_docs")
    return await process_document(req_id=req_id, file=file)

@router.post(
    "/interact_agent",
    status_code=status.HTTP_201_CREATED,
    response_model=InteractAgentResponse,
)
async def interact_agent(payload: InteractAgentRequest,db: DbSession,) -> InteractAgentResponse:
    conversation_id = payload.conversation_id 
    req_id = datetime.now().strftime(f"{conversation_id}-%H%M%d%m%y")
    agent_response = await run_agent(
        db,
        req_id=req_id,
        user_query=payload.user_query,
        conversation_id=payload.conversation_id,
    )
    return InteractAgentResponse(
        agent_response=agent_response,
        user_query=payload.user_query,
        req_id=req_id,
    )


@router.get(
    "/conversations/{conversation_id}/history",
    response_model=ConversationHistoryResponse,
)
async def get_conversation_history(
    conversation_id: Annotated[str, PathParam(min_length=1, max_length=255)],
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> ConversationHistoryResponse:
    request = ConversationHistoryRequest(
        conversation_id=conversation_id,
        limit=limit,
    )
    req_id = f"{conversation_id}-{datetime.now():%H%M%d%m%y}-get_history"
    return await fetch_conversation_history(db, req_id, request)
