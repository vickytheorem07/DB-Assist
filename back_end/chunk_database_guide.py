"""Load the database guide and create LangChain page-scoped chunks."""
import argparse
import json
from pathlib import Path

from app.services.loaders import DocumentLoader


DATA_DIR = Path(__file__).with_name('data')
DEFAULT_SOURCE = DATA_DIR / 'sales_management_db_details.docx'
DEFAULT_OUTPUT = DATA_DIR / 'sales_management_chunks.jsonl'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--max-tokens', type=int, default=500)
    parser.add_argument('--overlap-tokens', type=int, default=250)
    parser.add_argument('--encoding', default='cl100k_base',
                        help='tiktoken encoding; set this to match the target model')
    args = parser.parse_args()
    if args.max_tokens < 1 or args.overlap_tokens < 0 or args.overlap_tokens >= args.max_tokens:
        parser.error('require max-tokens > overlap-tokens >= 0')

    loader = DocumentLoader()
    page_documents = loader.load_docx_pages(args.source)
    chunks = loader.chunk_documents(
        page_documents,
        chunk_size=args.max_tokens,
        chunk_overlap=args.overlap_tokens,
        encoding_name=args.encoding,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('w', encoding='utf-8') as output_file:
        for chunk in chunks:
            output_file.write(json.dumps({
                'text': chunk.page_content,
                'metadata': chunk.metadata,
            }, ensure_ascii=False) + '\n')

    print(f'Wrote {len(chunks)} LangChain chunks to {args.output}')
    for chunk in chunks:
        metadata = chunk.metadata
        print('page={page} name={name} chunk={chunk_index} tokens={token_count}'.format(**metadata))


if __name__ == '__main__':
    main()
