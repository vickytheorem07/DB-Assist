

from pathlib import Path
from time import perf_counter
from typing import Any, TypedDict

from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_groq import ChatGroq
from pydantic import SecretStr
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage

from app.core.logger import setup_logger
from app.core.config import settings
from app.models.history import ConversationHistory
from app.services.prompts import agent_instructions
from app.services.vector_db import ChromaVectorDB
from app.services.embedding import Hugging_face_embedding
from fastapi import HTTPException, status
YAML_CONFIG_PATH = Path(__file__).resolve().parents[2] / "db_assist.yaml"
HISTORY_LIMIT = settings.limit_history_of_conversation

 
class AgentInput(TypedDict):
    """Input shape for the LangChain create_agent graph."""

    messages: list[AnyMessage | dict[str, Any]]

def load_database_config() -> tuple[str, list[str]]:
    """Read the PostgreSQL schema and allowed table names from YAML."""
    if not YAML_CONFIG_PATH.is_file():
        raise FileNotFoundError(
            f"YAML config not found: {YAML_CONFIG_PATH}. "
            "Create it using the example at the top of this file."
        )

    with YAML_CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)

    if not isinstance(config, dict) or not isinstance(config.get("database"), dict):
        raise ValueError("YAML config must contain a 'database' mapping.")

    database_config = config["database"]
    schema = database_config.get("schema")
    tables = database_config.get("tables")
    if not isinstance(schema, str) or not schema.strip():
        raise ValueError("Set a non-empty database.schema in the YAML config.")
    if (
        not isinstance(tables, list)
        or not tables
        or any(not isinstance(table, str) or not table.strip() for table in tables)
    ):
        raise ValueError("database.tables must be a non-empty list of table names.")

    return schema.strip(), [table.strip() for table in tables]



async def interact_agent(db: AsyncSession, req_id: str, user_query: str, conversation_id: str) -> str:
    logger = setup_logger(__name__, req_id)
    request_started = perf_counter()
    response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    original_user_query = user_query

    logger.info("Agent request started: conversation_id=%s", conversation_id)

    try:
        if not user_query or not user_query.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="user_query must not be empty",
            )
        if not conversation_id or not conversation_id.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="conversation_id must not be empty",
            )
        if not settings.DATABASE_URL:
            logger.error("DATABASE_URL is not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection is not configured",
            )

        llm = ChatGroq(
            model=settings.llm_model_name,
            temperature=settings.temperature,
            api_key=SecretStr(settings.groq_llm_api_key),
        )

        context = ""
        try:
            embedding = Hugging_face_embedding(
                settings.huggingface_embedding_model_name,
                settings.huggingface_api,
            )
            vector_db = ChromaVectorDB(
                embedding.embedding,
                settings.collection_name,
                settings.persist_dir,
            )
            relevant_docs = vector_db.similarity_search(user_query, k=settings.top_k)
            logger.info(
                "Semantic retrieval completed: result_count=%d collection=%s",
                len(relevant_docs),
                settings.collection_name,
            )
            for rank, document in enumerate(relevant_docs, start=1):
                logger.info(
                    "Retrieved document: rank=%d id=%s source=%s",
                    rank,
                    document.id,
                    document.metadata.get("source", "unknown"),
                )
            context = "\n\n".join(
                f"[Source: {document.metadata.get('source', 'unknown')}]\n{document.page_content}"
                for document in relevant_docs
            )
            user_query = f"user query: {user_query}\n\nContext:\n{context}"
        except Exception:
            # The SQL agent can still answer database questions if retrieval is unavailable.
            logger.exception("Semantic retrieval failed; continuing without retrieved context")

        schema_name, table_names = load_database_config()
        database = SQLDatabase.from_uri(
            settings.DATABASE_URL,
            include_tables=table_names,
        )
        allowed_tables = ", ".join(f"{schema_name}.{table}" for table in table_names)
        system_prompt = agent_instructions(
            schema_name=schema_name,
            allowed_tables=allowed_tables,
        )
        toolkit = SQLDatabaseToolkit(db=database, llm=llm)

        from langchain.agents import create_agent

        agent = create_agent(
            model=llm,
            tools=toolkit.get_tools(),
            system_prompt=system_prompt,
        )

        agent_started = perf_counter()
        try:
            history_result = await db.execute(
                select(ConversationHistory)
                .where(
                    ConversationHistory.conversation_id == conversation_id,
                    ConversationHistory.role.in_(("user", "assistant")),
                )
                .order_by(ConversationHistory.message_id.desc())
                .limit(HISTORY_LIMIT)
            )
            history_rows = list(reversed(history_result.scalars().all()))
        except Exception as exc:
            await db.rollback()
            logger.exception("Could not fetch conversation history")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not load conversation history",
            ) from exc

        logger.info(
            "Conversation history fetched: conversation_id=%s message_count=%d limit=%d",
            conversation_id,
            len(history_rows),
            HISTORY_LIMIT,
        )
        agent_messages: list[AnyMessage | dict[str, Any]] = [
            HumanMessage(content=message.content)
            if message.role == "user"
            else AIMessage(content=message.content)
            for message in history_rows
        ]
        agent_messages.append(HumanMessage(content=user_query))
        starting_message_count = len(agent_messages)
        agent_input: AgentInput = {"messages": agent_messages}

        try:
            agent_result = await agent.ainvoke(agent_input)
        except Exception as exc:
            logger.exception("Agent execution failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The database assistant could not complete the request",
            ) from exc

        final_message = next(
            (
                message
                for message in reversed(agent_result["messages"])
                if isinstance(message, AIMessage) and not message.tool_calls
            ),
            None,
        )
        if final_message is None:
            logger.error("Agent returned no final assistant message")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The database assistant returned no answer",
            )

        if isinstance(final_message.content, str):
            agent_output = final_message.content
        else:
            agent_output = "\n".join(
                block.get("text", "")
                for block in final_message.content
                if isinstance(block, dict) and block.get("type") == "text"
            )

        if not agent_output.strip():
            logger.error("Agent returned an empty assistant response")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The database assistant returned an empty answer",
            )

        db.add_all(
            [
                ConversationHistory(
                    conversation_id=conversation_id,
                    role="user",
                    content=original_user_query,
                ),
                ConversationHistory(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=agent_output,
                ),
            ]
        )
        try:
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.exception("Could not persist conversation exchange")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not save conversation history",
            ) from exc

        messages = agent_result["messages"][starting_message_count:]
        ai_messages = [message for message in messages if isinstance(message, AIMessage)]
        tool_call_count = sum(len(message.tool_calls or []) for message in ai_messages)
        completed_tool_count = sum(isinstance(message, ToolMessage) for message in messages)
        input_tokens = 0
        output_tokens = 0
        for message in ai_messages:
            usage = message.usage_metadata or message.response_metadata.get("token_usage", {})
            input_tokens += usage.get("input_tokens", usage.get("prompt_tokens", 0))
            output_tokens += usage.get("output_tokens", usage.get("completion_tokens", 0))

        logger.info(
            "Agent observability: llm_calls=%d tool_calls=%d tool_results=%d "
            "input_tokens=%d output_tokens=%d elapsed_seconds=%.3f",
            len(ai_messages),
            tool_call_count,
            completed_tool_count,
            input_tokens,
            output_tokens,
            perf_counter() - agent_started,
        )
        for message in messages:
            if isinstance(message, AIMessage):
                for tool_call in message.tool_calls or []:
                    logger.info(
                        "Agent tool call: name=%s",
                        tool_call.get("name", "unknown"),
                    )
            elif isinstance(message, ToolMessage):
                logger.info(
                    "Agent tool result: name=%s content_length=%d",
                    message.name,
                    len(str(message.content)),
                )

        response_status = status.HTTP_200_OK
        logger.info("Agent request completed successfully")
        return agent_output
    except HTTPException as exc:
        response_status = exc.status_code
        logger.warning(
            "Agent request failed: status_code=%d detail=%s",
            exc.status_code,
            exc.detail,
        )
        raise
    except (FileNotFoundError, ValueError) as exc:
        logger.exception("Agent configuration is invalid")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database assistant configuration is invalid",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected agent request failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request",
        ) from exc
    finally:
        logger.info(
            "Agent request ended: status_code=%d total_time_seconds=%.3f",
            response_status,
            perf_counter() - request_started,
        )

if __name__ == "__main__":
    import asyncio
    import sys

    from app.db.session import AsyncSessionLocal

    async def run_example() -> None:
        async with AsyncSessionLocal() as session:
            await interact_agent(
                session,
                "unit_test",
                "How many customers are in the database?",
                conversation_id="test_conversation",
            )

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(run_example())
