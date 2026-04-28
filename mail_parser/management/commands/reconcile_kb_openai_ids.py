"""Reconcile KnowledgeBaseCase.openai_file_id with files already in OpenAI.

After the data migration, every KnowledgeBaseCase row has an empty
`openai_file_id`. The corresponding `case_NNNNN.md` files already exist in
the OpenAI vector store from the legacy bulk sync — this command finds them
by filename and writes the file_id back to the DB row, so future edits and
deletes correctly replace/remove the right OpenAI file (no orphans).
"""
import openai
from django.conf import settings
from django.core.management.base import BaseCommand

from mail_parser.models import KnowledgeBaseCase


class Command(BaseCommand):
    help = 'Map existing OpenAI files (case_NNNNN.md) back to KnowledgeBaseCase rows.'

    def handle(self, *args, **options):
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=120.0)

        # 1. Collect all assistants files matching case_NNNNN.md
        self.stdout.write('Listing OpenAI files…')
        filename_to_id = {}
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
                    filename_to_id[fn] = f.id
            if not getattr(page, 'has_more', False):
                break
            after = page.data[-1].id
        self.stdout.write(f'  found {len(filename_to_id)} OpenAI files matching case_*.md')

        # 2. For each DB case, set openai_file_id from the map (if empty)
        cases = KnowledgeBaseCase.objects.filter(openai_file_id='')
        total = cases.count()
        self.stdout.write(f'Reconciling {total} cases without openai_file_id…')

        matched = 0
        for case in cases.iterator(chunk_size=500):
            file_id = filename_to_id.get(case.filename)
            if file_id:
                case.openai_file_id = file_id
                case.save(update_fields=['openai_file_id'])
                matched += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Reconciled {matched}/{total} cases.'
        ))
        unmatched = total - matched
        if unmatched:
            self.stdout.write(self.style.WARNING(
                f'{unmatched} cases have no matching OpenAI file '
                '(they will be uploaded as new files when first edited or via bulk_resync_kb_cases).'
            ))
