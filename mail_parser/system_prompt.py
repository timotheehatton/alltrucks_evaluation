"""Runtime prompt loader.

Single source of truth is the active `PromptVersion` row in the DB.
Falls back to the bundled `default_system_prompt.txt` only when the DB
hasn't been seeded yet (fresh install before migrations).

Cached for 60s via the Django cache framework — short enough that an
admin edit propagates within the minute, long enough to skip a DB hit
per AI call. `invalidate_cache()` lets the views push a change instantly
on the dyno that handled the request.
"""

import os

from django.core.cache import cache

_PATH = os.path.join(os.path.dirname(__file__), 'default_system_prompt.txt')
_CACHE_KEY = 'mail_parser:active_system_prompt'
_CACHE_TTL = 60


def get_system_prompt():
    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return cached

    # Local import to avoid a circular import at module load (models.py
    # eventually imports system_prompt.py via the PromptVersion.activate
    # method).
    from .models import PromptVersion

    active = (
        PromptVersion.objects
        .filter(is_active=True)
        .order_by('-activated_at')
        .first()
    )
    if active and active.content:
        cache.set(_CACHE_KEY, active.content, _CACHE_TTL)
        return active.content

    # Fallback for environments where the data migration hasn't run.
    with open(_PATH, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    cache.set(_CACHE_KEY, content, _CACHE_TTL)
    return content


def invalidate_cache():
    """Drop the cached prompt so the next AI call re-reads the DB.

    Called from admin handlers after Save / Activate so the new prompt
    takes effect immediately on the dyno that handled the request (other
    dynos catch up within the cache TTL).
    """
    cache.delete(_CACHE_KEY)
