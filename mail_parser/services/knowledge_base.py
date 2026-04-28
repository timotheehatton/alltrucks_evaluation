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


# ---------------------------------------------------------------------------
# Per-case CRUD helpers (used by the new admin page)
# ---------------------------------------------------------------------------


def _get_client():
    return openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=120.0)


def upload_case_to_openai(case):
    """Upload `case.to_markdown()` as a single file and attach it to the vector store.

    If the case already had an `openai_file_id`, the previous file is detached
    and deleted after the new one is indexed. Persists `openai_file_id`,
    `synced_at`, `sync_error` on the case.

    Returns (success: bool, error: str | None).
    """
    vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', None)
    if not vector_store_id:
        return False, 'OPENAI_VECTOR_STORE_ID is not configured.'

    client = _get_client()
    old_file_id = case.openai_file_id

    try:
        new_file = client.files.create(
            file=(case.filename, case.to_markdown().encode('utf-8')),
            purpose='assistants',
        )
        vs_file = client.vector_stores.files.create_and_poll(
            vector_store_id=vector_store_id,
            file_id=new_file.id,
            chunking_strategy=CHUNKING_STRATEGY,
        )
        if vs_file.status != 'completed':
            err = f'Indexing did not complete: status={vs_file.status}'
            case.sync_error = err
            case.save(update_fields=['sync_error'])
            try:
                client.files.delete(new_file.id)
            except Exception:
                pass
            return False, err

        if old_file_id and old_file_id != new_file.id:
            try:
                client.vector_stores.files.delete(file_id=old_file_id, vector_store_id=vector_store_id)
            except Exception:
                pass
            try:
                client.files.delete(old_file_id)
            except Exception:
                pass

        case.openai_file_id = new_file.id
        case.synced_at = timezone.now()
        case.sync_error = ''
        case.save(update_fields=['openai_file_id', 'synced_at', 'sync_error'])
        return True, None

    except Exception as e:
        case.sync_error = f'{type(e).__name__}: {e}'
        case.save(update_fields=['sync_error'])
        return False, case.sync_error


def delete_case_from_openai(case):
    """Detach + delete the case's OpenAI file. Idempotent."""
    if not case.openai_file_id:
        return True, None
    vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', None)
    if not vector_store_id:
        return False, 'OPENAI_VECTOR_STORE_ID is not configured.'
    client = _get_client()
    try:
        client.vector_stores.files.delete(file_id=case.openai_file_id, vector_store_id=vector_store_id)
    except Exception:
        pass
    try:
        client.files.delete(case.openai_file_id)
    except Exception:
        pass
    case.openai_file_id = ''
    case.save(update_fields=['openai_file_id'])
    return True, None


def bulk_resync_cases(queryset, on_progress=None):
    """Re-upload each case in `queryset` to OpenAI.

    Used by the bulk_resync_kb_cases command after a fresh DB load. Returns
    a `(uploaded, failed)` tuple.
    """
    uploaded = failed = 0
    total = queryset.count()
    for i, case in enumerate(queryset.order_by('case_number'), 1):
        ok, _ = upload_case_to_openai(case)
        if ok:
            uploaded += 1
        else:
            failed += 1
        if on_progress:
            on_progress({'done': i, 'total': total, 'uploaded': uploaded, 'failed': failed})
    return uploaded, failed