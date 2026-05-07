"""System prompt loader.

The prompt is intentionally hard-coded in `default_system_prompt.txt` and
loaded once per process. Editing the prompt requires a code change and a
deploy — there is no admin UI to edit it at runtime.
"""

import functools
import os

_PATH = os.path.join(os.path.dirname(__file__), 'default_system_prompt.txt')


@functools.lru_cache(maxsize=1)
def get_system_prompt():
    with open(_PATH, 'r', encoding='utf-8') as f:
        return f.read().strip()