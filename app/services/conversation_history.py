from time import perf_counter

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import setup_logger
from app.models.history import ConversationHistory
from app.schemas.conversation_history import (
    ConversationHistoryMessage,
    ConversationHistoryRequest,
    ConversationHistoryResponse,
)


async def fetch_conversation_history(
    db: AsyncSession,
    req_id: str,
    request: ConversationHistoryRequest,
) -> ConversationHistoryResponse:
    logger = setup_logger(__name__, req_id)
    started_at = perf_counter()
    logger.info(
        "Conversation history request started: conversation_id=%s limit=%d",
        request.conversation_id,
        request.limit,
    )

    try:
        result = await db.execute(
            select(ConversationHistory)
            .where(
                ConversationHistory.conversation_id == request.conversation_id,
                ConversationHistory.role.in_(("user", "assistant")),
            )
            .order_by(ConversationHistory.message_id.desc())
            .limit(request.limit)
        )
        rows = list(reversed(result.scalars().all()))
        messages = [ConversationHistoryMessage.model_validate(row) for row in rows]
        response = ConversationHistoryResponse(
            conversation_id=request.conversation_id,
            count=len(messages),
            messages=messages,
        )
        logger.info(
            "Conversation history request completed: conversation_id=%s count=%d elapsed_seconds=%.3f",
            request.conversation_id,
            len(messages),
            perf_counter() - started_at,
        )
        return response
    except Exception as exc:
        await db.rollback()
        logger.exception(
            "Conversation history fetch failed: conversation_id=%s",
            request.conversation_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve conversation history",
        ) from exc
