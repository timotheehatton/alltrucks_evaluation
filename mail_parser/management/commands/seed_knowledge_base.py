"""Seed the KnowledgeBaseFile singleton from the on-disk markdown file."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from mail_parser.models import KnowledgeBaseFile
from mail_parser.services.knowledge_base import count_cases


DEFAULT_PATH = Path(settings.BASE_DIR) / 'scripts' / 'alltrucks_hotline_kb.md'


class Command(BaseCommand):
    help = 'Load the markdown KB file from disk into the KnowledgeBaseFile singleton.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            default=str(DEFAULT_PATH),
            help='Path to the markdown KB file to load.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite even if the DB already has content.',
        )

    def handle(self, *args, **options):
        path = Path(options['file'])
        force = options['force']
        if not path.exists():
            self.stderr.write(self.style.ERROR(f'File not found: {path}'))
            return

        kb = KnowledgeBaseFile.load()
        if kb.content and not force:
            self.stdout.write(self.style.WARNING(
                'KnowledgeBaseFile already has content — use --force to overwrite.'
            ))
            return

        content = path.read_text(encoding='utf-8')
        kb.content = content
        kb.filename = path.name
        kb.byte_size = len(content.encode('utf-8'))
        kb.case_count = count_cases(content)
        kb.uploaded_at = timezone.now()
        kb.save()

        self.stdout.write(self.style.SUCCESS(
            f'Loaded {kb.case_count} cases ({kb.byte_size} B) from {path}'
        ))
