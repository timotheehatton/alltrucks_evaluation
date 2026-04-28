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


def sync_to_openai(kb, *, wipe=True, on_progress=None):
    """Sync the KB to OpenAI by uploading one file per case.

    Each case gets its own OpenAI file (named `case_<n>.md`) attached to the
    configured vector store, so each case becomes its own embedding unit.

    If `wipe=True`, all previously-attached files are detached + deleted before
    the new upload. If `wipe=False`, only the missing cases are uploaded
    (resumable mode — useful when a previous sync was partial).

    `on_progress(stats)` is called after each batch with a dict of running
    counters: {'uploaded', 'failed', 'cases_total', 'batch_done', 'batch_total'}.

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
        if wipe:
            _detach_and_delete_existing_files(client, vector_store_id)
            cases_to_upload = cases
        else:
            existing_filenames = _list_existing_filenames(client, vector_store_id)
            cases_to_upload = [
                (n, t) for n, t in cases
                if f'case_{n:05d}.md' not in existing_filenames
            ]

        stats = {
            'uploaded': 0,
            'failed': 0,
            'cases_total': len(cases_to_upload),
            'batch_done': 0,
            'batch_total': (len(cases_to_upload) + UPLOAD_BATCH_SIZE - 1) // UPLOAD_BATCH_SIZE,
        }

        for batch_start in range(0, len(cases_to_upload), UPLOAD_BATCH_SIZE):
            batch = cases_to_upload[batch_start:batch_start + UPLOAD_BATCH_SIZE]
            files = [
                (f'case_{case_no:05d}.md', text.encode('utf-8'))
                for case_no, text in batch
            ]
            result = client.vector_stores.file_batches.upload_and_poll(
                vector_store_id=vector_store_id,
                files=files,
                chunking_strategy=CHUNKING_STRATEGY,
            )
            counts = getattr(result, 'file_counts', None)
            if counts is not None:
                stats['uploaded'] += getattr(counts, 'completed', 0) or 0
                stats['failed'] += getattr(counts, 'failed', 0) or 0
            stats['batch_done'] += 1
            if on_progress:
                on_progress(stats)

        kb.openai_file_id = ''
        kb.vector_store_id = vector_store_id
        kb.last_synced_at = timezone.now()
        kb.sync_status = kb.SYNC_IDLE
        kb.sync_error = '' if stats['failed'] == 0 else f'{stats["failed"]} files failed during upload'
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


def _list_existing_filenames(client, vector_store_id):
    """Return the set of filenames already uploaded as 'assistants' files.

    We use the global Files API and filter by the `case_NNNNN.md` pattern,
    which is significantly faster than retrieving each vector-store file
    individually. Any matching filename in the account is treated as already
    uploaded — that's safe because no other workflow uses this naming.
    """
    names = set()
    after = None
    while True:
        kwargs = {'purpose': 'assistants', 'limit': 10000}
        if after:
            kwargs['after'] = after
        page = client.files.list(**kwargs)
        if not page.data:
            break
        for f in page.data:
            fn = getattr(f, 'filename', '') or ''
            if fn.startswith('case_') and fn.endswith('.md'):
                names.add(fn)
        if not getattr(page, 'has_more', False):
            break
        after = page.data[-1].id
    return names