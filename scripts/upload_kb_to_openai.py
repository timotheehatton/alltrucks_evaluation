"""Bootstrap script — kept for reference only.

The ongoing source of truth for the knowledge base is now the admin page at
`/admin/knowledge-base/`. The chunking constants below are duplicated from
`mail_parser/services/knowledge_base.py` (CHUNK_MAX_TOKENS / CHUNK_OVERLAP_TOKENS).

Use this script only to create a brand-new vector store. To re-sync the
existing one, use the admin UI.

Requires OPENAI_API_KEY environment variable.

Usage:
    python scripts/upload_kb_to_openai.py
    python scripts/upload_kb_to_openai.py --name "Custom Name"
"""
import argparse
import sys
import time
from pathlib import Path

from openai import OpenAI

SCRIPT_DIR = Path(__file__).resolve().parent
KB_PATH = SCRIPT_DIR / 'alltrucks_hotline_kb.md'

DEFAULT_NAME = 'Alltrucks Hotline Knowledge Base'
CHUNK_MAX_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 50


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', default=DEFAULT_NAME, help='Vector store display name.')
    parser.add_argument('--file', default=str(KB_PATH), help='Path to the markdown Knowledge Base file.')
    args = parser.parse_args()

    kb_path = Path(args.file)
    if not kb_path.exists():
        print(f'ERROR: file not found: {kb_path}', file=sys.stderr)
        sys.exit(1)

    client = OpenAI()

    print(f'Uploading file: {kb_path} ({kb_path.stat().st_size / 1024 / 1024:.1f} MB)')
    file_obj = client.files.create(
        file=open(kb_path, 'rb'),
        purpose='assistants',
    )
    print(f'  file id: {file_obj.id}')

    print(f'Creating vector store: "{args.name}"')
    vs = client.vector_stores.create(name=args.name)
    print(f'  vector store id: {vs.id}')

    print(f'Indexing file with chunk size={CHUNK_MAX_TOKENS}, overlap={CHUNK_OVERLAP_TOKENS}...')
    started = time.time()
    vs_file = client.vector_stores.files.create_and_poll(
        vector_store_id=vs.id,
        file_id=file_obj.id,
        chunking_strategy={
            'type': 'static',
            'static': {
                'max_chunk_size_tokens': CHUNK_MAX_TOKENS,
                'chunk_overlap_tokens': CHUNK_OVERLAP_TOKENS,
            },
        },
    )
    elapsed = time.time() - started

    print(f'  status: {vs_file.status} (in {elapsed:.1f}s)')
    if vs_file.status != 'completed':
        print('  ERROR: indexing did not complete cleanly')
        if getattr(vs_file, 'last_error', None):
            print(f'  last_error: {vs_file.last_error}')
        sys.exit(1)

    print()
    print('=' * 60)
    print(f'  Vector Store ID: {vs.id}')
    print(f'  File ID:         {file_obj.id}')
    print('=' * 60)
    print('Use the Vector Store ID in your agent / FileSearchTool config.')


if __name__ == '__main__':
    main()