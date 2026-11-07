from pathlib import Path
from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logger import setup_logger
from app.services.loaders import DocumentLoader

router = APIRouter()
logger = setup_logger(__name__)


@router.post("/load_doc", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)):
    log_filename = Path(file.filename or "unnamed").name.replace("\r", "").replace("\n", "")
    logger.info("Document upload received: filename=%s", log_filename)

    # Validate file extension
    if not (file.filename or "").lower().endswith(".docx"):
        logger.warning("Document upload rejected: unsupported file type, filename=%s", log_filename)
        raise HTTPException(
            status_code=400,
            detail="Only .docx files are allowed"
        )

    try:
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
        
        # Load one LangChain Document per page, including table-cell text.
        loader = DocumentLoader()
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

        return {
            "status": "success",
            "filename": file.filename,
            "message": "Document loaded and chunked successfully.",
            "pages": page_count,
            "chunks": len(chunks),
            "table_names": sorted({chunk.metadata["name"] for chunk in chunks}),
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("DOCX processing failed: filename=%s", log_filename)
        raise HTTPException(
            status_code=500,
            detail="Error processing document"
        )

    finally:
        await file.close()
