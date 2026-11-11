"""Load Word documents as page-level LangChain Documents and chunk them."""
from pathlib import Path
from typing import BinaryIO

import tiktoken
from docx import Document as WordDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logger import setup_logger


class DocumentLoader:
    """Read one table page per Document, then split oversized pages."""

    def __init__(self, req_id: str = "N/A") -> None:
        self.logger = setup_logger(__name__, req_id)

    def load_docx_pages(
        self,
        source: str | Path | BinaryIO,
        source_name: str | None = None,
    ) -> list[Document]:
        """Load a DOCX path or binary stream as one LangChain Document per page."""
        if isinstance(source, (str, Path)):
            source = Path(source)
            if source.suffix.lower() != ".docx":
                raise ValueError(f"Only Word .docx files are supported: {source.name}")
            source_name = source_name or source.name
            docx_input: str | BinaryIO = str(source)
        else:
            source_name = source_name or "uploaded.docx"
            docx_input = source

        self.logger.info("DOCX page extraction started: source=%s", source_name)
        try:
            word_document = WordDocument(docx_input)
            page_blocks: list[tuple[str, str | None]] = []
            documents: list[Document] = []

            def append_page() -> None:
                if not page_blocks:
                    return
                table_name = next(
                    (text.strip().lower() for text, style in page_blocks
                     if style is not None and style.startswith("Heading 1")),
                    None,
                )
                if not table_name:
                    raise ValueError(
                        f"No Heading 1 table name found on page {len(documents) + 1} "
                        f"in {source_name}"
                    )
                documents.append(Document(
                    page_content="\n".join(text for text, _ in page_blocks),
                    metadata={
                        "name": table_name,
                        "page": len(documents) + 1,
                        "source": source_name,
                    },
                ))
                page_blocks.clear()

            for child in word_document.element.body.iterchildren():
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    paragraph = Paragraph(child, word_document)
                    if paragraph.paragraph_format.page_break_before and page_blocks:
                        append_page()
                    if paragraph._p.xpath('.//w:br[@w:type="page"]'):
                        append_page()
                        continue
                    value = paragraph.text.strip()
                    if value:
                        style = paragraph.style.name if paragraph.style is not None else None
                        page_blocks.append((value, style))
                elif tag == "tbl":
                    table = Table(child, word_document)
                    for row in table.rows:
                        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                        if any(cells):
                            page_blocks.append((" | ".join(cells), ""))

            append_page()
        except Exception:
            self.logger.exception("DOCX page extraction failed: source=%s", source_name)
            raise
        self.logger.info("DOCX page extraction completed: source=%s pages=%d", source_name, len(documents))
        return documents

    def chunk_documents(
        self,
        page_documents: list[Document],
        chunk_size: int = 500,
        chunk_overlap: int = 250,
        encoding_name: str = "cl100k_base",
    ) -> list[Document]:
        """Keep each page intact unless oversized; overlap only within that page."""
        if chunk_size < 1 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("Require chunk_size > chunk_overlap >= 0")
        if not page_documents:
            self.logger.info("Document chunking skipped: page_count=0")
            return []

        self.logger.info(
            "Document chunking started: page_count=%d chunk_size=%d chunk_overlap=%d",
            len(page_documents),
            chunk_size,
            chunk_overlap,
        )
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=encoding_name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )
        chunks = splitter.split_documents(page_documents)
        encoding = tiktoken.get_encoding(encoding_name)
        page_chunk_indices: dict[int, int] = {}

        for chunk in chunks:
            page_number = chunk.metadata["page"]
            chunk_index = page_chunk_indices.get(page_number, 0)
            page_chunk_indices[page_number] = chunk_index + 1
            chunk.metadata["chunk_index"] = chunk_index
            chunk.metadata["token_count"] = len(encoding.encode(chunk.page_content))
            chunk.metadata["token_count_method"] = f"tiktoken:{encoding_name}"

        self.logger.info("Document chunking completed: page_count=%d chunk_count=%d", len(page_documents), len(chunks))
        return chunks

