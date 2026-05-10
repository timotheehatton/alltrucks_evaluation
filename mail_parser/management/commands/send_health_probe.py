"""Send one synthetic health probe.

Sends a marker email to `parse@ai.alltrucks-fleet-platform.com` (the only
inbound address) and pings OpenAI in the same tick. The email's round-trip
status is closed by either the inbound webhook signal (→ success) or the
`expire_old_probes` command after 30 minutes (→ timeout).

Run from Heroku Scheduler hourly.
"""
import secrets
import time
from datetime import datetime, timezone as dt_timezone

import openai
from django.conf import settings
from django.core.management.base import BaseCommand

from common.useful.email import email as email_service
from mail_parser.models import HealthCheckProbe

# The single inbound address routed via SendGrid Inbound Parse to
# /webhook/inbound-email/. Hard-coded — there is no other inbound on this
# project (see memory: "Single inbound email address").
PROBE_TO = 'parse@ai.alltrucks-fleet-platform.com'
PROBE_FROM = 'support@alltrucks-fleet-platform.com'


class Command(BaseCommand):
    help = 'Send one synthetic health probe (email round-trip + OpenAI ping).'

    def handle(self, *args, **options):
        token = secrets.token_hex(8)
        probe = HealthCheckProbe.objects.create(probe_token=token)
        self.stdout.write(f'Created probe {token}')

        # 1) Send the marker email
        subject = f'[HEALTHCHECK {token}] Synthetic monitor'
        timestamp = datetime.now(dt_timezone.utc).isoformat()
        body = (
            f'This is an automated health probe.\n\n'
            f'Token: {token}\n'
            f'Sent at: {timestamp}\n\n'
            f'It is sent every hour by Heroku Scheduler to verify that the '
            f'SendGrid Inbound Parse → Heroku → DB pipeline is alive. If you '
            f'are reading this, you can safely ignore or delete it.'
        )
        ok, msg_id, err = email_service.send_auto_reply(
            to_email=PROBE_TO,
            subject=subject,
            html_content=f'<pre>{body}</pre>',
            plain_text_content=body,
            from_email=PROBE_FROM,
        )
        probe.sendgrid_message_id = msg_id or ''
        if not ok:
            probe.status = HealthCheckProbe.STATUS_SEND_FAILED
            probe.error_message = (err or 'unknown SendGrid error')[:2000]
            self.stdout.write(self.style.ERROR(f'  email send FAILED: {err}'))
        else:
            self.stdout.write(f'  email sent (X-Message-Id={msg_id})')

        # 2) Ping OpenAI (always run, even if email send failed)
        t0 = time.time()
        try:
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, timeout=15.0)
            list(client.models.list().data)[:1]  # auth + connectivity
            probe.openai_models_ok = True
            vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', None)
            if vector_store_id:
                client.vector_stores.retrieve(vector_store_id)
                probe.openai_vector_store_ok = True
            probe.openai_status = HealthCheckProbe.OPENAI_STATUS_SUCCESS
            self.stdout.write(self.style.SUCCESS('  openai ping OK'))
        except Exception as e:
            probe.openai_status = HealthCheckProbe.OPENAI_STATUS_FAILED
            probe.openai_error = f'{type(e).__name__}: {e}'[:2000]
            self.stdout.write(self.style.ERROR(f'  openai ping FAILED: {e}'))
        probe.openai_latency_seconds = time.time() - t0

        probe.save()
        self.stdout.write(f'Probe {token} saved (status={probe.status}).')
