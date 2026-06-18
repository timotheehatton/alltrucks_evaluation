"""Seed the PromptVersion table from default_system_prompt.txt.

Run once, after `0034_add_promptversion`. Idempotent — skips if any
PromptVersion already exists. After this migration the runtime prompt
is sourced from the DB; the file stays as a fallback for fresh
installs that haven't migrated yet.
"""
import os

from django.db import migrations
from django.utils import timezone


def seed_prompt(apps, schema_editor):
    PromptVersion = apps.get_model('mail_parser', 'PromptVersion')
    if PromptVersion.objects.exists():
        return

    file_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'default_system_prompt.txt',
    )
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
    except FileNotFoundError:
        content = ''

    PromptVersion.objects.create(
        content=content,
        label='initial seed',
        notes='Seeded from default_system_prompt.txt by migration 0035.',
        is_active=True,
        activated_at=timezone.now(),
    )


def unseed(apps, schema_editor):
    PromptVersion = apps.get_model('mail_parser', 'PromptVersion')
    PromptVersion.objects.filter(label='initial seed').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mail_parser', '0034_add_promptversion'),
    ]

    operations = [
        migrations.RunPython(seed_prompt, reverse_code=unseed),
    ]
