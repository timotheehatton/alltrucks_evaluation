"""Populate KnowledgeBaseCase rows from the legacy `KnowledgeBaseFile.content` blob.

Reuses the same parsing logic the build script used (regex-driven), so case
numbers stay aligned with the OpenAI file naming `case_NNNNN.md`.
"""
import re

from django.db import migrations


CASE_PATTERN = re.compile(r'^## Case (\d+):', re.M)


def _split_into_cases(content):
    matches = list(CASE_PATTERN.finditer(content))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        case_no = int(m.group(1))
        text = content[start:end].rstrip()
        if text.endswith('---'):
            text = text[:-3].rstrip()
        yield case_no, text


def _bullet(text, label):
    """Extract `- **Label:** value` content from a case markdown block."""
    pattern = rf'^- \*\*{re.escape(label)}:\*\*\s*(.+?)\s*$'
    m = re.search(pattern, text, re.M)
    return m.group(1).strip() if m else ''


def _section(text, header):
    """Return the body of a `### Header` section, stripped of any **Subject:** / **Summary:** prefix lines."""
    pattern = rf'^### {re.escape(header)}\s*\n(.*?)(?=^### |\Z)'
    m = re.search(pattern, text, re.M | re.DOTALL)
    if not m:
        return '', ''
    body = m.group(1).strip()
    # Strip leading **Subject:** or **Summary:** prefix line, capture it
    prefix = ''
    prefix_match = re.match(r'\*\*(?:Subject|Summary):\*\*\s*([^\n]*)\n?', body)
    if prefix_match:
        prefix = prefix_match.group(1).strip()
        body = body[prefix_match.end():].strip()
    return prefix, body


def parse_case(case_no, text):
    issue_subject, issue_body = _section(text, 'Issue')
    resolution_summary, resolution_body = _section(text, 'Resolution')
    return {
        'case_number': case_no,
        'manufacturer': _bullet(text, 'Manufacturer'),
        'series': _bullet(text, 'Series'),
        'engine': _bullet(text, 'Engine'),
        'registration_date': _bullet(text, 'Registration date'),
        'vin': _bullet(text, 'VIN'),
        'mileage': _bullet(text, 'Mileage'),
        'axle_configuration': _bullet(text, 'Axle configuration'),
        'abs_configuration': _bullet(text, 'ABS configuration'),
        'installed_system': _bullet(text, 'Installed system'),
        'system': _bullet(text, 'System'),
        'country': _bullet(text, 'Country'),
        'request_type': _bullet(text, 'Request type') or 'Fehlersuche am Fahrzeug',
        'subject': issue_subject,
        'issue': issue_body,
        'resolution_summary': resolution_summary,
        'resolution': resolution_body,
        # OpenAI files were uploaded with case_NNNNN.md naming → assume each
        # case_number maps to an existing file; fill openai_file_id later via
        # a one-shot reconciliation if needed.
        'openai_file_id': '',
    }


def populate_cases(apps, schema_editor):
    KnowledgeBaseFile = apps.get_model('mail_parser', 'KnowledgeBaseFile')
    KnowledgeBaseCase = apps.get_model('mail_parser', 'KnowledgeBaseCase')

    if KnowledgeBaseCase.objects.exists():
        # Idempotent: don't double-populate if rerun
        return

    kb = KnowledgeBaseFile.objects.filter(pk=1).first()
    if not kb or not kb.content:
        return

    objects = [
        KnowledgeBaseCase(**parse_case(no, text))
        for no, text in _split_into_cases(kb.content)
    ]
    KnowledgeBaseCase.objects.bulk_create(objects, batch_size=500)


def reverse_populate(apps, schema_editor):
    KnowledgeBaseCase = apps.get_model('mail_parser', 'KnowledgeBaseCase')
    KnowledgeBaseCase.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('mail_parser', '0022_knowledgebasecase'),
    ]
    operations = [
        migrations.RunPython(populate_cases, reverse_populate),
    ]
