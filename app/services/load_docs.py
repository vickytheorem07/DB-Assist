from pathlib import Path
from io import BytesIO
from datetime import datetime
from time import perf_counter

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logger import setup_logger
from app.services.loaders import DocumentLoader
from app.services.embedding import Hugging_face_embedding
from app.services.vector_db import ChromaVectorDB
from app.schemas.load_docs import LoadDocsResponse

async def load_docs(req_id: str, file: UploadFile) -> LoadDocsResponse:
    logger = setup_logger(__name__, req_id)
    request_started = perf_counter()
    response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    log_filename = Path(file.filename or "unnamed").name.replace("\r", "").replace("\n", "")
    logger.info("/load_doc request started: filename=%s", log_filename)

    try:
        # Validate file extension
        if not (file.filename or "").lower().endswith(".docx"):
            logger.warning("Document upload rejected: unsupported file type, filename=%s", log_filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .docx files are allowed"
            )

        # Read no more than the configured maximum plus one byte.
        max_upload_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        contents = await file.read(max_upload_bytes + 1)
        if len(contents) > max_upload_bytes:
            logger.warning(
                "Document upload rejected: size exceeds limit, filename=%s limit_mb=%d",
                log_filename,
                settings.MAX_UPLOAD_SIZE_MB,
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Document exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB upload limit",
            )
        
        # Load one LangChain Document per page.
        loader = DocumentLoader(req_id=req_id)
        page_documents = loader.load_docx_pages(
            BytesIO(contents),
            source_name=log_filename,
        )
        page_count = len(page_documents)
        if page_count > settings.MAX_DOCUMENT_PAGES:
            logger.warning(
                "Document upload rejected: page count exceeds limit, filename=%s pages=%d limit=%d",
                log_filename,
                page_count,
                settings.MAX_DOCUMENT_PAGES,
            )
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Document exceeds the {settings.MAX_DOCUMENT_PAGES} page limit",
            )

        #chunking 
        chunks = loader.chunk_documents(
            page_documents,
            chunk_size=settings.CHUNK_SIZE_TOKENS,
            chunk_overlap=settings.CHUNK_OVERLAP_TOKENS,
            encoding_name=settings.TIKTOKEN_ENCODING,
        )
        extracted_chars = sum(len(page.page_content) for page in page_documents)
        logger.info(
            "DOCX loaded and chunked: filename=%s size_bytes=%d pages=%d chunks=%d extracted_chars=%d",
            log_filename,
            len(contents),
            page_count,
            len(chunks),
            extracted_chars,
        )

        #Store the chunks in the vector database
        embedding = Hugging_face_embedding(
            settings.huggingface_embedding_model_name,
            settings.huggingface_api,
            req_id=req_id,
        )
        vector_db = ChromaVectorDB(
            embedding.embedding,
            settings.collection_name,
            settings.persist_dir,
            req_id=req_id,
        )
        inserted_ids = vector_db.add_documents(chunks)
        logger.info("DOCX chunks stored: filename=%s inserted_count=%d", log_filename, len(inserted_ids))
        response_status = status.HTTP_201_CREATED
        return LoadDocsResponse(
            status="success",
            filename=file.filename,
            message="Document loaded, chunked and stored in vector db successfully.",
            pages=page_count,
            chunks=len(chunks),
            table_names=sorted({chunk.metadata["name"] for chunk in chunks}),
        )

    except HTTPException as exc:
        response_status = exc.status_code
        raise
    except Exception:
        logger.exception("DOCX processing failed: filename=%s", log_filename)
        response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        raise HTTPException(
            status_code=500,
            detail="Error processing document"
        )

    finally:
        try:
            await file.close()
        finally:
            logger.info(
                "/load_doc request ended: status_code=%d total_time_seconds=%.2f",
                response_status,
                perf_counter() - request_started,
            )
