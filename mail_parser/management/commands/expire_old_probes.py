"""Mark health probes still pending after 30 minutes as `timeout`.

Run from Heroku Scheduler every 10 minutes. Without this, a probe whose
inbound webhook never comes back (because the receive pipeline is broken)
would stay forever in `pending` and the stats page would falsely report
the service as operational.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mail_parser.models import HealthCheckProbe

TIMEOUT_MINUTES = 30


class Command(BaseCommand):
    help = 'Flag probes still pending after 30 minutes as timeout.'

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(minutes=TIMEOUT_MINUTES)
        expired = HealthCheckProbe.objects.filter(
            status=HealthCheckProbe.STATUS_PENDING,
            sent_at__lt=threshold,
        ).update(status=HealthCheckProbe.STATUS_TIMEOUT)
        self.stdout.write(f'Expired {expired} probe(s).')
