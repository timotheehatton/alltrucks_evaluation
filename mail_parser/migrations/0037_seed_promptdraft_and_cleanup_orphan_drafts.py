"""Seed the singleton PromptDraft and drop orphan draft PromptVersion rows.

Before this migration the editor created a new PromptVersion every time
the operator clicked "Save draft", so the history table accumulated
versions that were never published. We now keep only published versions
in PromptVersion (the audit trail) and one mutable PromptDraft row for
the work-in-progress prompt.

A row is an "orphan draft" iff it was never activated, identified by
`activated_at IS NULL`. Real published versions always carry an
activation timestamp.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    PromptVersion = apps.get_model('mail_parser', 'PromptVersion')
    PromptDraft = apps.get_model('mail_parser', 'PromptDraft')

    active = PromptVersion.objects.filter(is_active=True).order_by('-activated_at').first()
    initial_content = active.content if active else ''

    draft, _ = PromptDraft.objects.get_or_create(pk=1)
    draft.content = initial_content
    draft.save()

    PromptVersion.objects.filter(activated_at__isnull=True).delete()


def backwards(apps, schema_editor):
    PromptDraft = apps.get_model('mail_parser', 'PromptDraft')
    PromptDraft.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mail_parser', '0036_promptdraft'),
    ]

    operations = [
        migrations.RunPython(forwards, reverse_code=backwards),
    ]
