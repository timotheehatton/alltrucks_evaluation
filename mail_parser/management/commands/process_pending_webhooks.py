"""Re-process inbound webhooks that got stuck in `status='received'`.

The post_save signal kicks off processing in a daemon thread; if the
worker dyno restarts mid-thread (or anything else swallows the work),
the webhook stays in `status='received'` forever. This command sweeps
every 10 minutes and re-runs the pipeline on anything stuck for >5 min.

Idempotent: re-runnable on already-processed webhooks. Skip rows without
a sender (catch-all dumps from the view's emergency path).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mail_parser.models import InboundWebhook
from mail_parser.signals import _process_webhook_async

STUCK_THRESHOLD_MINUTES = 5


class Command(BaseCommand):
    help = "Re-process webhooks stuck in status='received' for >5 minutes."

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(minutes=STUCK_THRESHOLD_MINUTES)
        stuck = InboundWebhook.objects.filter(
            status=InboundWebhook.STATUS_RECEIVED,
            received_at__lt=threshold,
        ).exclude(sender='')
        count = 0
        for w in stuck:
            self.stdout.write(f'Re-processing webhook #{w.id} (received {w.received_at})')
            _process_webhook_async(w.id)
            count += 1
        self.stdout.write(f'Re-processed {count} stuck webhook(s).')
