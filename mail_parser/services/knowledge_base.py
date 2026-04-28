"""Knowledge Base ↔ OpenAI vector store synchronization."""
import re

import openai
from django.conf import settings
from django.utils import timezone

CHUNK_MAX_TOKENS = 200
CHUNK_OVERLAP_TOKENS = 20

CHUNKING_STRATEGY = {
    'type': 'static',
    'static': {
        'max_chunk_size_tokens': CHUNK_MAX_TOKENS,
        'chunk_overlap_tokens': CHUNK_OVERLAP_TOKENS,
    },
}


def count_cases(text):
    """Count `## Case ...` headings in the markdown content."""
    if not text:
        return 0
    return len(re.findall(r'^## Case ', text, re.M))


def sync_to_openai(kb):
    """Push the current KnowledgeBaseFile content to the configured vector store.

    - Uploads kb.content as a new OpenAI file.
    - Attaches it to settings.OPENAI_VECTOR_STORE_ID with the standard chunking
      strategy and waits for indexing to complete.
    - Detaches and deletes the previously linked file (if any).
    - Persists openai_file_id, vector_store_id, last_synced_at, sync_status, sync_error.

    Returns (success: bool, error: str | None).
    """
    if not kb.content:
        return False, 'Knowledge Base is empty — upload a file first.'

    vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', None)
    if not vector_store_id:
        return False, 'OPENAI_VECTOR_STORE_ID is not configured.'

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=120.0)
    filename = kb.filename or 'alltrucks_hotline_kb.md'

    try:
        new_file = client.files.create(
            file=(filename, kb.content.encode('utf-8')),
            purpose='assistants',
        )

        vs_file = client.vector_stores.files.create_and_poll(
            vector_store_id=vector_store_id,
            file_id=new_file.id,
            chunking_strategy=CHUNKING_STRATEGY,
        )
        if vs_file.status != 'completed':
            error = f'Indexing did not complete: status={vs_file.status}'
            if getattr(vs_file, 'last_error', None):
                error += f' | last_error={vs_file.last_error}'
            kb.sync_status = kb.SYNC_FAILED
            kb.sync_error = error
            kb.save(update_fields=['sync_status', 'sync_error'])
            try:
                client.files.delete(new_file.id)
            except Exception:
                pass
            return False, error

        old_id = kb.openai_file_id
        if old_id and old_id != new_file.id:
            try:
                client.vector_stores.files.delete(file_id=old_id, vector_store_id=vector_store_id)
            except Exception:
                pass
            try:
                client.files.delete(old_id)
            except Exception:
                pass

        kb.openai_file_id = new_file.id
        kb.vector_store_id = vector_store_id
        kb.last_synced_at = timezone.now()
        kb.sync_status = kb.SYNC_IDLE
        kb.sync_error = ''
        kb.save(update_fields=[
            'openai_file_id', 'vector_store_id', 'last_synced_at',
            'sync_status', 'sync_error',
        ])
        return True, None

    except openai.APIError as e:
        kb.sync_status = kb.SYNC_FAILED
        kb.sync_error = f'OpenAI API error: {e}'
        kb.save(update_fields=['sync_status', 'sync_error'])
        return False, kb.sync_error
    except Exception as e:
        kb.sync_status = kb.SYNC_FAILED
        kb.sync_error = f'{type(e).__name__}: {e}'
        kb.save(update_fields=['sync_status', 'sync_error'])
        return False, kb.sync_error
