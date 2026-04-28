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

# Number of files uploaded per batch when syncing per-case.
# OpenAI's vector_stores.file_batches caps individual batches; 100 is a safe
# value that keeps each batch small enough to retry on partial failures.
UPLOAD_BATCH_SIZE = 100


def count_cases(text):
    """Count `## Case ...` headings in the markdown content."""
    if not text:
        return 0
    return len(re.findall(r'^## Case ', text, re.M))


def split_into_cases(content):
    """Yield (case_number, case_markdown) pairs from the KB content.

    Each case is the substring starting at `## Case N:` and ending right before
    the next `## Case ` heading (or end of content). Trailing `---` separators
    are dropped.
    """
    pattern = re.compile(r'^## Case (\d+):', re.M)
    matches = list(pattern.finditer(content))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        case_no = int(m.group(1))
        text = content[start:end].rstrip()
        # Trim trailing horizontal rule
        if text.endswith('---'):
            text = text[:-3].rstrip()
        yield case_no, text


def _detach_and_delete_existing_files(client, vector_store_id):
    """Remove every file currently attached to the vector store."""
    after = None
    deleted = 0
    while True:
        kwargs = {'vector_store_id': vector_store_id, 'limit': 100}
        if after:
            kwargs['after'] = after
        page = client.vector_stores.files.list(**kwargs)
        ids = [f.id for f in page.data]
        if not ids:
            break
        for fid in ids:
            try:
                client.vector_stores.files.delete(file_id=fid, vector_store_id=vector_store_id)
            except Exception:
                pass
            try:
                client.files.delete(fid)
            except Exception:
                pass
            deleted += 1
        if not page.has_more:
            break
        after = ids[-1]
    return deleted


def sync_to_openai(kb):
    """Sync the KB to OpenAI by uploading one file per case.

    Each case gets its own OpenAI file (named `case_<n>.md`) attached to the
    configured vector store, so each case becomes its own embedding unit. This
    eliminates the positional bias and cross-case bleed that affected the
    previous single-file approach.

    Returns (success: bool, error: str | None).
    """
    if not kb.content:
        return False, 'Knowledge Base is empty — upload a file first.'

    vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', None)
    if not vector_store_id:
        return False, 'OPENAI_VECTOR_STORE_ID is not configured.'

    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=600.0)

    cases = list(split_into_cases(kb.content))
    if not cases:
        return False, 'No `## Case` sections found in the content.'

    try:
        # Wipe everything currently attached
        _detach_and_delete_existing_files(client, vector_store_id)

        # Upload per-case files in batches
        for batch_start in range(0, len(cases), UPLOAD_BATCH_SIZE):
            batch = cases[batch_start:batch_start + UPLOAD_BATCH_SIZE]
            files = [
                (f'case_{case_no:05d}.md', text.encode('utf-8'))
                for case_no, text in batch
            ]
            client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=files,
                chunking_strategy=CHUNKING_STRATEGY,
            )

        kb.openai_file_id = ''  # not meaningful in per-file mode
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