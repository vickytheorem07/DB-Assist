# DB-Assist
An AI-powered database assistant that converts natural language questions into SQL queries, executes them against databases, and delivers accurate, context-aware results in a human-readable format. Built using LLMs, LangChain, and FastAPI to simplify database interactions and enable efficient data retrieval without requiring SQL expertise.

## Load and chunk the database guide

The document service in `back_end/app/services/loaders.py` accepts Word `.docx` files and returns one LangChain `Document` per manually paginated page. It includes Word table cells and stores the table heading in `metadata["name"]`, along with the page number and source filename.

Install the project dependencies and generate the JSONL chunk file with:

```powershell
uv sync
uv run python back_end/chunk_database_guide.py --max-tokens 500 --overlap-tokens 250 --encoding cl100k_base
```

The LangChain splitter keeps each page separate and only subdivides a page when it exceeds the maximum token size. The overlap is applied between subchunks from that page. The encoding should match the model used by the application. Output is written to `back_end/data/sales_management_chunks.jsonl` by default.

## Upload limits

The API reads `MAX_DOCUMENT_PAGES` (default `10`), `MAX_UPLOAD_SIZE_MB` (default `10`), `CHUNK_SIZE_TOKENS` (default `500`), `CHUNK_OVERLAP_TOKENS` (default `250`), and `TIKTOKEN_ENCODING` (default `cl100k_base`) from application settings. Set these environment variables to change the page, upload-size, and chunking limits.
